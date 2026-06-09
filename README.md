# Remno-ApproveBot 🤖
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg?logo=telegram)](https://t.me)

**Remno ApproveBot** — это легковесный, быстрый и надежный Telegram-бот, разработанный для автоматического одобрения (или отклонения) входящих заявок на подписоку Remnowave. Идеальное решение для администраторов сообществ, позволяющее автоматизировать рутину и мгновенно принимать пользователей.

---

## ✨ Особенности

* 🔒 **Безопасность данных:** Конфиденциальная настройка через переменные окружения (`.env`).
* ⚙️ **Гибкая кастомизация:** Возможность отправки приветственного сообщения пользователю в ЛС после одобрения.

---

## 🚀 Быстрый старт

### Требования
Перед началом убедитесь, что у вас установлены:
* **Python 3.10+** или **Docker**
* Токен бота от [@BotFather](https://t.me/BotFather)

---

## 🛠️ Установка и запуск

1. Клонируйте репозиторий:

```bash
   git clone [https://github.com/kostiaprofrom/remno-approvebot.git](https://github.com/kostiaprofrom/remno-approvebot.git)
   cd remno-approvebot

```

2. Создайте и активируйте виртуальное окружение:
```bash
python -m venv venv
# Для Linux/macOS:
source venv/bin/activate
# Для Windows:
venv\\Scripts\\activate

```

3. Установите зависимости:
```bash
pip install -r requirements.txt

```

4. Создайте файл `.env` в корневой директории по шаблону:
```env
TELEGRAM_TOKEN=ваш_токен_бота
# Дополнительные настройки (если применимо в вашем коде)
WELCOME_MESSAGE="Привет! Твоя заявка успешно одобрена 🎉"

```

5. Запустите бота:
```bash
python app.py

```

---

## 🔧 Используемый стек

* **Язык:** Python 3.10+
* **Библиотека:** `aiogram 3.x` (или `pyTelegramBotAPI` / `python-telegram-bot`)
* **Окружение:** `python-dotenv`
