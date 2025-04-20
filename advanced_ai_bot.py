import logging
import requests
import re
from threading import Lock
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота
TELEGRAM_BOT_TOKEN = '7742884929:AAFsofcPRHme5SarsIdbn1bbnYfqhr0GyL0'

# Состояния для ConversationHandler
EMAIL, PASSWORD, REGISTER_EMAIL, REGISTER_PASSWORD = range(4)

# Хранилище пользователей (заглушка без БД) после log out или окончания сессии сбрасывается 
users = {}
users_lock = Lock()  # Thread-safe access to users dictionary

# Запрос к Ollama
def query_ollama(prompt: str) -> str:
    url = 'http://localhost:11434/api/generate'
    headers = {'Content-Type': 'application/json'}
    data = {
        "model": "llama2",
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json().get("response", "Нет ответа")
    except requests.exceptions.Timeout:
        logger.warning("Превышено время ожидания ответа от Ollama (30 секунд)")
        return "Я пока отдыхаю. Попробуй разбудить меня чуть попозже!"
    except requests.exceptions.ConnectionError:
        logger.error("Не удалось подключиться к Ollama: сервер не доступен")
        return "Ошибка: Ollama сервер недоступен. Проверьте подключение."
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к Ollama: {e}")
        return f"Ошибка: не удалось связаться с Ollama. Попробуйте позже."

# Проверка авторизации
def is_authorized(update: Update) -> bool:
    user_id = update.effective_user.id
    with users_lock:
        return any(user_data["telegram_id"] == user_id and user_data["telegram_id"] is not None
                   for user_data in users.values())

# Валидация email
def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

# Валидация пароля
def is_valid_password(password: str) -> bool:
    return len(password) >= 6

# Обработка команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Получена команда /start")
    welcome_message = (
        "Привет! Я бот с Llama 2. Я могу отвечать на ваши вопросы с помощью ИИ, но сначала нужно авторизоваться.\n"
        "Для подробной информации используйте /help.\n"
        "Команды:\n"
        "/start - Показать это сообщение\n"
        "/help - Показать справку и список команд\n"
        "/login - Войти в систему\n"
        "/register - Зарегистрироваться\n"
        "/exit - Выйти из системы"
    )
    await update.message.reply_text(welcome_message)
    if not is_authorized(update):
        await update.message.reply_text("Пожалуйста, войдите (/login) или зарегистрируйтесь (/register).")
    return ConversationHandler.END

# Обработка команды /help
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Получена команда /help")
    help_message = (
        "Я бот с Llama 2, созданный для ответа на ваши вопросы с использованием ИИ.\n"
        "Функциональность:\n"
        "- Отвечаю на текстовые запросы (до 100 символов) после авторизации.\n"
        "- Требуется регистрация и вход для использования.\n"
        "- Если ответ занимает больше 30 секунд, я попрошу подождать.\n"
        "Список команд:\n"
        "/start - Показать приветственное сообщение\n"
        "/help - Показать эту справку\n"
        "/login - Войти в систему (требуется email и пароль)\n"
        "/register - Зарегистрироваться (нужен email и пароль, минимум 6 символов)\n"
        "/exit - Выйти из системы\n"
        "/cancel - Отменить текущую операцию (во время входа или регистрации)"
    )
    await update.message.reply_text(help_message)

# Начало процесса входа
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_authorized(update):
        await update.message.reply_text("Вы уже авторизованы!")
        return ConversationHandler.END
    await update.message.reply_text("Введите ваш email:")
    return EMAIL

# Обработка email при входе
async def email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if not is_valid_email(email):
        await update.message.reply_text("Неверный формат email. Попробуйте еще раз.")
        return EMAIL
    context.user_data['email'] = email
    with users_lock:
        if email not in users:
            await update.message.reply_text("Email не найден. Попробуйте еще раз или зарегистрируйтесь (/register).")
            return EMAIL
    await update.message.reply_text("Введите пароль:")
    return PASSWORD

# Обработка пароля при входе
async def password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = context.user_data['email']
    password = update.message.text.strip()
    with users_lock:
        if email in users and users[email]["password"] == password:
            users[email]["telegram_id"] = update.effective_user.id
            await update.message.reply_text("Успешная авторизация! Теперь вы можете использовать бота.")
            return ConversationHandler.END
        else:
            await update.message.reply_text("Неверный пароль. Попробуйте еще раз.")
            return PASSWORD

# Начало процесса регистрации
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_authorized(update):
        await update.message.reply_text("Вы уже зарегистрированы и авторизованы!")
        return ConversationHandler.END
    await update.message.reply_text("Введите ваш email:")
    return REGISTER_EMAIL

# Обработка email при регистрации
async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if not is_valid_email(email):
        await update.message.reply_text("Неверный формат email. Попробуйте еще раз.")
        return REGISTER_EMAIL
    with users_lock:
        if email in users:
            await update.message.reply_text("Этот email уже зарегистрирован. Попробуйте другой или войдите (/login).")
            return REGISTER_EMAIL
    context.user_data['email'] = email
    await update.message.reply_text("Придумайте пароль (минимум 6 символов):")
    return REGISTER_PASSWORD

# Обработка пароля при регистрации
async def register_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = context.user_data['email']
    password = update.message.text.strip()
    if not is_valid_password(password):
        await update.message.reply_text("Пароль должен быть не короче 6 символов. Попробуйте еще раз.")
        return REGISTER_PASSWORD
    with users_lock:
        users[email] = {
            "password": password,
            "telegram_id": update.effective_user.id
        }
    await update.message.reply_text("Регистрация успешна! Теперь вы можете использовать бота.")
    return ConversationHandler.END

# Отмена диалога
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.")
    context.user_data.clear()  # Clear user_data to prevent stale data
    return ConversationHandler.END

# Обработка неожиданных команд в ConversationHandler
async def handle_unexpected_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Пожалуйста, завершите текущую операцию или используйте /cancel для отмены.")
    return None  # Keep the conversation state

# Обработка команды /exit
async def exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Получена команда /exit")
    user_id = update.effective_user.id
    with users_lock:
        for email, user_data in list(users.items()):  # Use list to avoid RuntimeError
            if user_data["telegram_id"] == user_id:
                users[email]["telegram_id"] = None
                await update.message.reply_text("Вы успешно вышли из системы. Войдите (/login) или зарегистрируйтесь (/register) снова.")
                logger.info(f"Пользователь {email} вышел")
                return
    await update.message.reply_text("Вы не авторизованы. Войдите (/login) или зарегистрируйтесь (/register).")

# Обработка обычных сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("Пожалуйста, войдите (/login) или зарегистрируйтесь (/register).")
        return
    
    user_message = update.message.text.strip()
    logger.info(f"Получено сообщение: {user_message}")
    
    # Check for empty or whitespace-only messages
    if not user_message:
        await update.message.reply_text("Ошибка: сообщение не может быть пустым.")
        return
    
    # Проверка длины сообщения
    if len(user_message) > 100:
        await update.message.reply_text("Ошибка: сообщение не должно превышать 100 символов.")
        return
    
    await update.message.chat.send_action(action="typing")
    reply = query_ollama(user_message)
    await update.message.reply_text(reply)

# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    logger.error(f"Ошибка: {error}")
    if update and update.message:
        if isinstance(error, requests.exceptions.Timeout):
            await update.message.reply_text("Я пока отдыхаю. Попробуй разбудить меня чуть попозже!")
        elif isinstance(error, requests.exceptions.ConnectionError):
            await update.message.reply_text("Ошибка: не удалось подключиться к Ollama.")
        else:
            await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

# Запуск бота
def main():
    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

        # ConversationHandler для входа
        login_conv = ConversationHandler(
            entry_points=[CommandHandler("login", login)],
            states={
                EMAIL: [
                    MessageHandler(filters.TEXT & (~filters.COMMAND), email),
                    MessageHandler(filters.COMMAND, handle_unexpected_command),
                ],
                PASSWORD: [
                    MessageHandler(filters.TEXT & (~filters.COMMAND), password),
                    MessageHandler(filters.COMMAND, handle_unexpected_command),
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        # ConversationHandler для регистрации
        register_conv = ConversationHandler(
            entry_points=[CommandHandler("register", register)],
            states={
                REGISTER_EMAIL: [
                    MessageHandler(filters.TEXT & (~filters.COMMAND), register_email),
                    MessageHandler(filters.COMMAND, handle_unexpected_command),
                ],
                REGISTER_PASSWORD: [
                    MessageHandler(filters.TEXT & (~filters.COMMAND), register_password),
                    MessageHandler(filters.COMMAND, handle_unexpected_command),
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel)],
        )

        # Добавление обработчиков
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help))
        app.add_handler(CommandHandler("exit", exit))
        app.add_handler(login_conv)
        app.add_handler(register_conv)
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        app.add_error_handler(error_handler)

        logger.info("Бот запущен")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == '__main__':
    main()