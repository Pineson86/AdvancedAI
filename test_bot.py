import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

# Импортируем функции из скрипта с ботом 
from bot import (
    start, help, login, email, password,
    register, register_email, register_password,
    cancel, exit, handle_message, handle_unexpected_command,
    is_authorized, is_valid_email, is_valid_password, query_ollama,
    users, users_lock # Доступ к users и users_lock для очистки/инициализации
)

# Сброс состояния users перед каждым тестом
@pytest.fixture(autouse=True)
def reset_users_state():
    with users_lock:
        users.clear()
    yield

# Фикстуры для мокирования объектов Telegram
@pytest.fixture
def mock_update():
    """Фикстура для имитации объекта Update."""
    update = AsyncMock()
    update.effective_user.id = 123
    update.message.chat.id = 123
    update.message.from_user.id = 123
    update.message.text = ""
    return update

@pytest.fixture
def mock_context():
    """Фикстура для имитации объекта ContextTypes.DEFAULT_TYPE."""
    context = AsyncMock()
    context.user_data = {}
    context.bot.send_message = AsyncMock()
    context.message = AsyncMock() # Добавляем для send_action
    context.chat = AsyncMock() # Добавляем для send_action
    context.bot.send_action = AsyncMock()
    return context

# Мокирование query_ollama для всех тестов, которые используют эту функцию
@pytest.fixture(autouse=True)
def mock_query_ollama_global():
    with patch('bot.query_ollama', return_value="Ответ от Ollama") as mock_ollama:
        yield mock_ollama

# --- Модульные тесты для вспомогательных функций ---

def test_is_valid_email_valid():
    assert is_valid_email("test@example.com") is True

def test_is_valid_email_invalid_format():
    assert is_valid_email("invalid-email") is False

def test_is_valid_email_missing_at():
    assert is_valid_email("testexample.com") is False

def test_is_valid_password_valid():
    assert is_valid_password("securepassword") is True

def test_is_valid_password_too_short():
    assert is_valid_password("short") is False

# --- Тесты для функции is_authorized ---

def test_is_authorized_not_authorized(mock_update):
    mock_update.effective_user.id = 456 # Пользователь не в users
    assert is_authorized(mock_update) is False

def test_is_authorized_authorized(mock_update):
    user_id = 123
    with users_lock:
        users["test@example.com"] = {"password": "password123", "telegram_id": user_id}
    mock_update.effective_user.id = user_id
    assert is_authorized(mock_update) is True

def test_is_authorized_user_exists_but_not_logged_in(mock_update):
    with users_lock:
        users["test@example.com"] = {"password": "password123", "telegram_id": None}
    assert is_authorized(mock_update) is False

# --- Тесты для команд и ConversationHandler ---

@pytest.mark.asyncio
async def test_start_command_unauthorized(mock_update, mock_context):
    await start(mock_update, mock_context)
    mock_update.message.reply_text.assert_any_call(
        "Привет! Я бот с Llama 2. Я могу отвечать на ваши вопросы с помощью ИИ, но сначала нужно авторизоваться.\n"
        "Для подробной информации используйте /help.\n"
        "Команды:\n"
        "/start - Показать это сообщение\n"
        "/help - Показать справку и список команд\n"
        "/login - Войти в систему\n"
        "/register - Зарегистрироваться\n"
        "/exit - Выйти из системы"
    )
    mock_update.message.reply_text.assert_called_with("Пожалуйста, войдите (/login) или зарегистрируйтесь (/register).")
    assert mock_update.message.reply_text.call_count == 2

@pytest.mark.asyncio
async def test_start_command_authorized(mock_update, mock_context):
    with users_lock:
        users["auth@example.com"] = {"password": "123456", "telegram_id": mock_update.effective_user.id}
    await start(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once() # Только приветственное сообщение, без запроса на логин/регистрацию

@pytest.mark.asyncio
async def test_help_command(mock_update, mock_context):
    await help(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    assert "Я бот с Llama 2" in mock_update.message.reply_text.call_args[0][0]

@pytest.mark.asyncio
async def test_login_command_unauthorized(mock_update, mock_context):
    result = await login(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Введите ваш email:")
    assert result == 0 # EMAIL state

@pytest.mark.asyncio
async def test_login_command_already_authorized(mock_update, mock_context):
    with users_lock:
        users["auth@example.com"] = {"password": "123456", "telegram_id": mock_update.effective_user.id}
    result = await login(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Вы уже авторизованы!")
    assert result == -1 # ConversationHandler.END

@pytest.mark.asyncio
async def test_email_valid(mock_update, mock_context):
    mock_update.message.text = "user@example.com"
    with users_lock:
        users["user@example.com"] = {"password": "password123", "telegram_id": None}
    result = await email(mock_update, mock_context)
    assert mock_context.user_data['email'] == "user@example.com"
    mock_update.message.reply_text.assert_called_with("Введите пароль:")
    assert result == 1 # PASSWORD state

@pytest.mark.asyncio
async def test_email_invalid_format(mock_update, mock_context):
    mock_update.message.text = "bad-email"
    result = await email(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Неверный формат email. Попробуйте еще раз.")
    assert result == 0 # EMAIL state (stay in current state)

@pytest.mark.asyncio
async def test_email_not_found(mock_update, mock_context):
    mock_update.message.text = "nonexistent@example.com"
    result = await email(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Email не найден. Попробуйте еще раз или зарегистрируйтесь (/register).")
    assert result == 0 # EMAIL state

@pytest.mark.asyncio
async def test_password_correct(mock_update, mock_context):
    mock_context.user_data['email'] = "user@example.com"
    mock_update.message.text = "password123"
    with users_lock:
        users["user@example.com"] = {"password": "password123", "telegram_id": None}
    result = await password(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Успешная авторизация! Теперь вы можете использовать бота.")
    assert users["user@example.com"]["telegram_id"] == mock_update.effective_user.id
    assert result == -1 # ConversationHandler.END

@pytest.mark.asyncio
async def test_password_incorrect(mock_update, mock_context):
    mock_context.user_data['email'] = "user@example.com"
    mock_update.message.text = "wrongpassword"
    with users_lock:
        users["user@example.com"] = {"password": "password123", "telegram_id": None}
    result = await password(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Неверный пароль. Попробуйте еще раз.")
    assert result == 1 # PASSWORD state (stay in current state)

@pytest.mark.asyncio
async def test_register_command_unauthorized(mock_update, mock_context):
    result = await register(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Введите ваш email:")
    assert result == 2 # REGISTER_EMAIL state

@pytest.mark.asyncio
async def test_register_command_already_authorized(mock_update, mock_context):
    with users_lock:
        users["auth@example.com"] = {"password": "123456", "telegram_id": mock_update.effective_user.id}
    result = await register(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Вы уже зарегистрированы и авторизованы!")
    assert result == -1 # ConversationHandler.END

@pytest.mark.asyncio
async def test_register_email_valid_new_email(mock_update, mock_context):
    mock_update.message.text = "newuser@example.com"
    result = await register_email(mock_update, mock_context)
    assert mock_context.user_data['email'] == "newuser@example.com"
    mock_update.message.reply_text.assert_called_with("Придумайте пароль (минимум 6 символов):")
    assert result == 3 # REGISTER_PASSWORD state

@pytest.mark.asyncio
async def test_register_email_invalid_format(mock_update, mock_context):
    mock_update.message.text = "invalid-register-email"
    result = await register_email(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Неверный формат email. Попробуйте еще раз.")
    assert result == 2 # REGISTER_EMAIL state

@pytest.mark.asyncio
async def test_register_email_already_registered(mock_update, mock_context):
    mock_update.message.text = "existing@example.com"
    with users_lock:
        users["existing@example.com"] = {"password": "password123", "telegram_id": None}
    result = await register_email(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Этот email уже зарегистрирован. Попробуйте другой или войдите (/login).")
    assert result == 2 # REGISTER_EMAIL state

@pytest.mark.asyncio
async def test_register_password_valid(mock_update, mock_context):
    mock_context.user_data['email'] = "brandnew@example.com"
    mock_update.message.text = "verysecurepassword"
    result = await register_password(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Регистрация успешна! Теперь вы можете использовать бота.")
    with users_lock:
        assert "brandnew@example.com" in users
        assert users["brandnew@example.com"]["password"] == "verysecurepassword"
        assert users["brandnew@example.com"]["telegram_id"] == mock_update.effective_user.id
    assert result == -1 # ConversationHandler.END

@pytest.mark.asyncio
async def test_register_password_too_short(mock_update, mock_context):
    mock_context.user_data['email'] = "brandnew@example.com"
    mock_update.message.text = "short"
    result = await register_password(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Пароль должен быть не короче 6 символов. Попробуйте еще раз.")
    assert result == 3 # REGISTER_PASSWORD state

@pytest.mark.asyncio
async def test_cancel_command(mock_update, mock_context):
    mock_context.user_data['email'] = "some@email.com" # Simulate ongoing conversation
    await cancel(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Действие отменено.")
    assert not mock_context.user_data # user_data should be cleared

@pytest.mark.asyncio
async def test_exit_command_authorized(mock_update, mock_context):
    with users_lock:
        users["logged_in@example.com"] = {"password": "123", "telegram_id": mock_update.effective_user.id}
    await exit(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with(
        "Вы успешно вышли из системы. Войдите (/login) или зарегистрируйтесь (/register) снова."
    )
    with users_lock:
        assert users["logged_in@example.com"]["telegram_id"] is None

@pytest.mark.asyncio
async def test_exit_command_not_authorized(mock_update, mock_context):
    await exit(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Вы не авторизованы. Войдите (/login) или зарегистрируйтесь (/register).")

@pytest.mark.asyncio
async def test_handle_message_unauthorized(mock_update, mock_context):
    mock_update.message.text = "привет"
    await handle_message(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Пожалуйста, войдите (/login) или зарегистрируйтесь (/register).")

@pytest.mark.asyncio
async def test_handle_message_authorized_valid_message(mock_update, mock_context, mock_query_ollama_global):
    with users_lock:
        users["auth@example.com"] = {"password": "123", "telegram_id": mock_update.effective_user.id}
    mock_update.message.text = "Какой сегодня день?"
    await handle_message(mock_update, mock_context)
    mock_update.message.chat.send_action.assert_called_once_with(action="typing")
    mock_query_ollama_global.assert_called_once_with("Какой сегодня день?")
    mock_update.message.reply_text.assert_called_once_with("Ответ от Ollama")

@pytest.mark.asyncio
async def test_handle_message_too_long(mock_update, mock_context):
    with users_lock:
        users["auth@example.com"] = {"password": "123", "telegram_id": mock_update.effective_user.id}
    mock_update.message.text = "a" * 101
    await handle_message(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Ошибка: сообщение не должно превышать 100 символов.")
    mock_update.message.chat.send_action.assert_not_called()

@pytest.mark.asyncio
async def test_handle_message_empty(mock_update, mock_context):
    with users_lock:
        users["auth@example.com"] = {"password": "123", "telegram_id": mock_update.effective_user.id}
    mock_update.message.text = ""
    await handle_message(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Ошибка: сообщение не может быть пустым.")
    mock_update.message.chat.send_action.assert_not_called()

@pytest.mark.asyncio
async def test_handle_unexpected_command(mock_update, mock_context):
    mock_update.message.text = "/login" # Unexpected command within a conversation state
    result = await handle_unexpected_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_with("Пожалуйста, завершите текущую операцию или используйте /cancel для отмены.")
    assert result is None # Stay in the same conversation state

# Тесты для обработки ошибок query_ollama
@pytest.mark.asyncio
async def test_query_ollama_timeout():
    with patch('requests.post', side_effect=requests.exceptions.Timeout):
        result = query_ollama("test")
        assert result == "Я пока отдыхаю. Попробуй разбудить меня чуть попозже!"

@pytest.mark.asyncio
async def test_query_ollama_connection_error():
    with patch('requests.post', side_effect=requests.exceptions.ConnectionError):
        result = query_ollama("test")
        assert result == "Ошибка: Ollama сервер недоступен. Проверьте подключение."

@pytest.mark.asyncio
async def test_query_ollama_generic_request_exception():
    with patch('requests.post', side_effect=requests.exceptions.RequestException):
        result = query_ollama("test")
        assert "Ошибка: не удалось связаться с Ollama" in result

@pytest.mark.asyncio
async def test_query_ollama_successful_response():
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Тестовый ответ от модели"}
    mock_response.raise_for_status.return_value = None # No exception
    with patch('requests.post', return_value=mock_response):
        result = query_ollama("какой-то запрос")
        assert result == "Тестовый ответ от модели"