<div align="center">

# 🌌 Remno-ApproveBot 🤖

[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg?logo=telegram)](https://t.me)

**Remno ApproveBot** — это Telegram-бот, разработанный для полной автоматизации продаж и продления подписок в панели управления Remnawave. Бот организует процесс ручной проверки чеков/скриншотов администратором, берет на себя автоматическое взаимодействие с API Remnawave (создание пользователей, продление подписок), а также включает в себя встроенную реферальную систему и планировщик уведомлений об окончании подписки.

</div>

---

## ✨ Особенности

* 💳 **Автоматизация подписок:** Интеграция с API Remnawave для мгновенного создания пользователей и продления подписок после апрува заявки.
* 👥 **Панель администратора:** Полноценный интерфейс внутри бота для просмотра активных/отключенных пользователей, пагинации списка и управления доступом (блокировка/разблокировка) в один клик.
* 🤝 **Реферальная система:** Уникальные пригласительные ссылки для пользователей с автоматическим начислением бонусных дней пригласителю после первой успешной оплаты друга.
* ⏰ **Умные напоминания:** Встроенный асинхронный шедулер, отправляющий уведомления пользователям за 3 дня и за 1 день до окончания срока действия подписки для предотвращения даунтайма.
* 📝 **Кастомизация текстов:** Все интерфейсные сообщения, шаблоны карточек и уведомлений вынесены в переменные окружения (`.env`) и полностью настраиваются без изменения кода.
* ⚙️ **Надежность и миграции:** Хранение данных в локальной БД SQLite через асинхронный `aiosqlite`. Система автоматически проверяет структуру таблиц при старте и накатывает миграции.

---

## 📋 Требования перед установкой

Перед началом работы убедитесь, что у вас есть:
1. Токен Telegram-бота, полученный у [@BotFather](https://t.me/BotFather).
2. Ваш Telegram ID (для выдачи прав администратора).
3. Токен администратора и URL вашей развернутой панели **Remnawave**.

---

## 🚀 Быстрый старт (Автоустановка)

Подключитесь к вашему серверу по SSH от имени `root` и выполните следующую команду:

```bash
bash <(curl -fsSL [https://raw.githubusercontent.com/kostiaprofrom/remno-approvebot/main/remnabotscrypt.sh](https://raw.githubusercontent.com/kostiaprofrom/remno-approvebot/main/remnabotscrypt.sh))
```

> 💡 **Встроенный менеджер управления**
> Этот скрипт не просто установит бота, но и добавит в вашу систему удобную панель управления `remnabot`. С её помощью вы сможете обновлять код в один клик, смотреть логи, редактировать настройки и автоматически создавать `.zip` бэкапы.
> 
> 📖 **[Читать подробную инструкцию по работе с менеджером](MANAGER_README.md)**

---

<details>
<summary><b>🛠 Нажмите, чтобы открыть инструкцию по ручной установке</b></summary>

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
venv\Scripts\activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` в корневой директории по шаблону:
```env
# Основные настройки Telegram
BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
ADMIN_ID=987654321
ACCESS_CODE=СЕКРЕТНЫЙ_КОД_СТАРТА

# Настройки интеграции Remnawave
REMNAWAVE_BASE_URL=[https://panel.yourdomain.com](https://panel.yourdomain.com)
REMNAWAVE_TOKEN=your_remnawave_api_token
REMNAWAVE_DEFAULT_SQUAD_UUID=your-squad-uuid-here

# Маркетинг и ссылки
CHAT_LINK=[https://t.me/your_community_chat](https://t.me/your_community_chat)
PAYMENT_LINK=[https://t.me/your_payment_gateway](https://t.me/your_payment_gateway)
REFERRAL_BONUS_DAYS=7

# Настройки планировщика и интерфейса
REMINDER_CHECK_INTERVAL_SECONDS=3600
ADMIN_USERS_PER_PAGE=8
HERO_IMAGE_PATH=assets/main_menu.jpg
WELCOME_IMAGE_PATH=assets/welcome.jpg

# Кастомизация текстов (Необязательно, поддерживается \n и HTML)
TEXT_ACCESS_PROMPT="🔐 <b>Доступ к боту закрыт</b>\n\nОтправьте код доступа."
```

5. Запустите бота:
```bash
python app.py
```

</details>

---

## 🔧 Используемый стек

* **Язык:** Python 3.10+
* **Библиотека:** `aiogram 3.x`
* **Окружение:** `python-dotenv`
* **База данных:** `aiosqlite`
