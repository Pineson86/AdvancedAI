# Telegram бот с Llama 2

Этот Telegram бот использует модель Llama 2 для ответа на текстовые запросы пользователей. Для использования бота необходимо пройти регистрацию или войти в существующий аккаунт.

## Функции бота:

* **Авторизация:**
    * **Регистрация:** Новые пользователи могут создать аккаунт, указав email и пароль (не менее 6 символов).
    * **Вход:** Зарегистрированные пользователи могут войти в систему, используя свой email и пароль.
    * **Выход:** Пользователи могут выйти из своей сессии.
* **Взаимодействие с Llama 2:**
    * После успешной авторизации бот принимает текстовые сообщения от пользователя (до 100 символов).
    * Запрос пользователя отправляется к локально запущенной модели Llama 2.
    * Бот отправляет ответ от Llama 2 пользователю.
    * В процессе ожидания ответа от Llama 2 бот показывает индикатор "печатает".
* **Информационные команды:**
    * `/start`: Выводит приветственное сообщение и список основных команд.
    * `/help`: Предоставляет подробную информацию о боте, его функциональности и список доступных команд.
* **Управление сессией:**
    * `/login`: Запускает процесс входа в систему.
    * `/register`: Запускает процесс регистрации нового пользователя.
    * `/exit`: Выполняет выход из текущей сессии пользователя.
    * `/cancel`: Отменяет текущий процесс входа или регистрации.
* **Обработка ошибок:**
    * Бот обрабатывает ситуации, когда Ollama недоступен или отвечает с задержкой.
    * Сообщает пользователю об ошибках при некорректном вводе данных (например, неверный формат email, короткий пароль, пустые сообщения, превышение лимита символов).

## Требования для запуска:

* Установленный Python 3.x
* Установленная библиотека `requests` (`pip install requests`)
* Установленная библиотека `python-telegram-bot` (`pip install python-telegram-bot --pre`)
* Локально запущенный Ollama с доступной моделью `llama2` (или настроенный другой URL и модель в скрипте).


