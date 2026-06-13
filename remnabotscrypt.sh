#!/bin/bash

# Настройки путей и репозитория
APP_DIR="/opt/remno-approvebot"
SERVICE_NAME="remnabot.service"
REPO_URL="https://github.com/kostiaprofrom/remno-approvebot.git"
SCRIPT_ALIAS="/usr/local/bin/remnabot"

# ==========================================
# Функции
# ==========================================

# Проверка прав root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo "Ошибка: Скрипт должен быть запущен с правами root (sudo)."
        exit 1
    fi
}

# Установка бота
install_bot() {
    check_root
    
    if [ -d "$APP_DIR" ]; then
        echo "Директория $APP_DIR уже существует. Если вы хотите переустановить бота, сначала удалите его через меню."
        read -n 1 -s -r -p "Нажмите любую клавишу для продолжения..."
        return
    fi

    echo "=== Обновление системы и установка зависимостей ==="
    apt update
    apt install -y git python3 python3-venv python3-pip curl nano

    echo "=== Клонирование репозитория ==="
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR" || exit

    echo "=== Настройка виртуального окружения ==="
    python3 -m venv venv
    source venv/bin/activate
    
    echo "=== Установка Python зависимостей ==="
    pip install -r requirements.txt

    echo "=== Настройка окружения (.env) ==="
    # Копируем пример файла конфигурации
    if [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    else
        echo "Предупреждение: файл .env.example не найден. Создаю пустой .env..."
        touch "$APP_DIR/.env"
    fi

    echo "Пожалуйста, введите необходимые данные:"
    read -p "BOT_TOKEN: " BOT_TOKEN
    read -p "ADMIN_ID: " ADMIN_ID
    read -p "ACCESS_CODE: " ACCESS_CODE
    read -p "REMNAWAVE_BASE_URL: " REMNAWAVE_BASE_URL
    read -p "REMNAWAVE_TOKEN: " REMNAWAVE_TOKEN
    read -p "REMNAWAVE_DEFAULT_SQUAD_UUID: " REMNAWAVE_DEFAULT_SQUAD_UUID

    # Заменяем значения в скопированном .env
    # Используем разделитель ~ для URL, чтобы избежать конфликтов со слешами в ссылках
    sed -i "s~^BOT_TOKEN=.*~BOT_TOKEN=$BOT_TOKEN~" "$APP_DIR/.env"
    sed -i "s~^ADMIN_ID=.*~ADMIN_ID=$ADMIN_ID~" "$APP_DIR/.env"
    sed -i "s~^ACCESS_CODE=.*~ACCESS_CODE=$ACCESS_CODE~" "$APP_DIR/.env"
    sed -i "s~^REMNAWAVE_BASE_URL=.*~REMNAWAVE_BASE_URL=$REMNAWAVE_BASE_URL~" "$APP_DIR/.env"
    sed -i "s~^REMNAWAVE_TOKEN=.*~REMNAWAVE_TOKEN=$REMNAWAVE_TOKEN~" "$APP_DIR/.env"
    sed -i "s~^REMNAWAVE_DEFAULT_SQUAD_UUID=.*~REMNAWAVE_DEFAULT_SQUAD_UUID=$REMNAWAVE_DEFAULT_SQUAD_UUID~" "$APP_DIR/.env"

    # Если каких-то переменных не было в .env.example, добавляем их в конец файла
    grep -q "^BOT_TOKEN=" "$APP_DIR/.env" || echo "BOT_TOKEN=$BOT_TOKEN" >> "$APP_DIR/.env"
    grep -q "^ADMIN_ID=" "$APP_DIR/.env" || echo "ADMIN_ID=$ADMIN_ID" >> "$APP_DIR/.env"
    grep -q "^ACCESS_CODE=" "$APP_DIR/.env" || echo "ACCESS_CODE=$ACCESS_CODE" >> "$APP_DIR/.env"
    grep -q "^REMNAWAVE_BASE_URL=" "$APP_DIR/.env" || echo "REMNAWAVE_BASE_URL=$REMNAWAVE_BASE_URL" >> "$APP_DIR/.env"
    grep -q "^REMNAWAVE_TOKEN=" "$APP_DIR/.env" || echo "REMNAWAVE_TOKEN=$REMNAWAVE_TOKEN" >> "$APP_DIR/.env"
    grep -q "^REMNAWAVE_DEFAULT_SQUAD_UUID=" "$APP_DIR/.env" || echo "REMNAWAVE_DEFAULT_SQUAD_UUID=$REMNAWAVE_DEFAULT_SQUAD_UUID" >> "$APP_DIR/.env"

    echo "Файл .env успешно настроен."

    echo "=== Создание службы systemctl ==="
    cat > /etc/systemd/system/$SERVICE_NAME <<EOF
[Unit]
Description=Remno Approve Telegram Bot
After=network.target

[Service]
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable $SERVICE_NAME
    systemctl start $SERVICE_NAME

    # Создание алиаса команды для вызова меню
    if [ "$(realpath "$0")" != "$SCRIPT_ALIAS" ]; then
        cp "$0" "$SCRIPT_ALIAS"
        chmod +x "$SCRIPT_ALIAS"
        echo "=== Готово! ==="
        echo "Меню управления установлено. Теперь вы можете вызывать его командой: remnabot"
    fi

    echo "Установка успешно завершена, бот запущен!"
    read -n 1 -s -r -p "Нажмите любую клавишу для возврата в меню..."
}

# Удаление бота
remove_bot() {
    check_root
    echo "Вы уверены, что хотите полностью удалить бота, все его данные и скрипт управления? (y/n)"
    read -r ans
    if [[ "$ans" =~ ^[Yy]$ ]]; then
        echo "Остановка и удаление службы..."
        systemctl stop $SERVICE_NAME 2>/dev/null
        systemctl disable $SERVICE_NAME 2>/dev/null
        rm /etc/systemd/system/$SERVICE_NAME 2>/dev/null
        systemctl daemon-reload
        
        echo "Удаление файлов бота..."
        rm -rf $APP_DIR
        
        echo "Удаление системного скрипта (remnabot)..."
        rm -f "$SCRIPT_ALIAS"
        
        echo "Удаление завершено. Программа завершает работу."
        exit 0
    else
        echo "Отмена."
        read -n 1 -s -r -p "Нажмите любую клавишу для продолжения..."
    fi
}

# Управление службой
manage_bot() {
    check_root
    action=$1
    echo "Выполняю: systemctl $action $SERVICE_NAME..."
    systemctl "$action" $SERVICE_NAME
    
    if [ "$action" == "status" ]; then
        echo ""
        read -n 1 -s -r -p "Нажмите любую клавишу для возврата в меню..."
    else
        echo "Готово."
        sleep 1
    fi
}

# Редактирование .env
edit_env() {
    check_root
    if [ -f "$APP_DIR/.env" ]; then
        nano "$APP_DIR/.env"
        echo "Конфигурация изменена. Перезапустить бота для применения изменений? (y/n)"
        read -r ans
        if [[ "$ans" =~ ^[Yy]$ ]]; then
            manage_bot restart
        fi
    else
        echo "Файл .env не найден. Бот уже установлен?"
        read -n 1 -s -r -p "Нажмите любую клавишу для продолжения..."
    fi
}

# Главное меню
show_menu() {
    while true; do
        clear
        echo "========================================="
        echo "       Управление Remno Approve Bot      "
        echo "========================================="
        echo "1. Установить бота"
        echo "2. Удалить бота и меню (remnabot)"
        echo "-----------------------------------------"
        echo "3. Запустить бота (Start)"
        echo "4. Остановить бота (Stop)"
        echo "5. Перезапустить бота (Restart)"
        echo "6. Статус бота (Status)"
        echo "-----------------------------------------"
        echo "7. Настройки (редактировать .env)"
        echo "0. Выход"
        echo "========================================="
        read -p "Выберите действие [0-7]: " choice

        case $choice in
            1) install_bot ;;
            2) remove_bot ;;
            3) manage_bot start ;;
            4) manage_bot stop ;;
            5) manage_bot restart ;;
            6) manage_bot status ;;
            7) edit_env ;;
            0) echo "Выход."; exit 0 ;;
            *) echo "Неверный выбор. Попробуйте снова."; sleep 1 ;;
        esac
    done
}

# ==========================================
# Точка входа
# ==========================================

if [ "$EUID" -ne 0 ]; then
    echo "ВНИМАНИЕ: Скрипт запущен не от root. Большинство команд не сработают!"
    sleep 2
fi

show_menu