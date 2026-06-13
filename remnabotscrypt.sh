#!/bin/bash

# ==============================================================================
# REMNO APPROVE BOT MANAGER
# Автоматизированный скрипт для управления ботом
# ==============================================================================

# --- КОНФИГУРАЦИЯ И СИСТЕМНЫЕ ПУТИ ---
APP_DIR="/opt/remno-approvebot"
SERVICE_NAME="remnabot.service"
REPO_URL="https://github.com/kostiaprofrom/remno-approvebot.git"
SCRIPT_PATH="/usr/local/bin/remnabot"

# --- ЦВЕТА И ЭСТЕТИКА (ANSI Escape-коды) ---
RESET=$'\033[0m'
BOLD=$'\033[1m'
DIM=$'\033[2m'
RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
BLUE=$'\033[34m'
MAGENTA=$'\033[35m'
CYAN=$'\033[36m'
WHITE=$'\033[37m'

# --- ФУНКЦИИ ВЫВОДА ЛОГОВ ---
info() { echo -e "${CYAN}➜ ${RESET}${BOLD}$1${RESET}"; }
success() { echo -e "${GREEN}✔ ${RESET}${BOLD}$1${RESET}"; }
warn() { echo -e "${YELLOW}⚠ ${RESET}${BOLD}$1${RESET}"; }
error() { echo -e "${RED}✖ ${RESET}${BOLD}$1${RESET}"; }

# --- ОТРИСОВКА ЗАГОЛОВКА ---
draw_banner() {
    clear
    echo -e "${MAGENTA}${BOLD}╭────────────────────────────────────────────────────╮"
    echo -e "│             R E M N O   A P P R O V E              │"
    echo -e "│                 Bot Manager v1.2                   │"
    echo -e "╰────────────────────────────────────────────────────╯${RESET}"
}

# ==============================================================================
# СИСТЕМНЫЕ ФУНКЦИИ И УТИЛИТЫ
# ==============================================================================

check_deps() {
    local deps=(git python3 python3-venv python3-pip curl nano)
    info "Проверка системных зависимостей..."
    
    export DEBIAN_FRONTEND=noninteractive
    apt-get update >/dev/null 2>&1
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null && ! dpkg -l | grep -q "^ii  $dep "; then
            echo -e "   ${DIM}Установка пакета: $dep...${RESET}"
            apt-get install -yq "$dep" >/dev/null 2>&1
        fi
    done
    success "Все зависимости успешно проверены!"
}

# ==============================================================================
# ПРОЦЕСС УСТАНОВКИ
# ==============================================================================

install_bot() {
    draw_banner
    if [ -d "$APP_DIR" ]; then
        warn "Бот уже установлен в $APP_DIR."
        echo -e "${DIM}Если вы хотите переустановить его, сначала сделайте удаление.${RESET}"
        sleep 2
        return
    fi

    info "Инициализация мастера установки..."
    check_deps

    info "Клонирование репозитория GitHub..."
    git clone -q "$REPO_URL" "$APP_DIR"
    
    # ФИКС ОШИБКИ PIP
    sed -i '/^logging/d' "$APP_DIR/requirements.txt"
    
    info "Настройка виртуального окружения Python..."
    python3 -m venv "$APP_DIR/venv"
    source "$APP_DIR/venv/bin/activate"
    
    info "Установка зависимостей (requirements.txt)..."
    pip install -q -r "$APP_DIR/requirements.txt"

    info "Настройка конфигурации (.env)..."
    if [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    else
        touch "$APP_DIR/.env"
    fi

    echo -e "\n${BOLD}Пожалуйста, введите необходимые данные:${RESET}"
    read -r -p "BOT_TOKEN: " BOT_TOKEN
    read -r -p "ADMIN_ID: " ADMIN_ID
    read -r -p "ACCESS_CODE: " ACCESS_CODE
    read -r -p "REMNAWAVE_BASE_URL: " REMNAWAVE_BASE_URL
    read -r -p "REMNAWAVE_TOKEN: " REMNAWAVE_TOKEN
    read -r -p "REMNAWAVE_DEFAULT_SQUAD_UUID: " REMNAWAVE_DEFAULT_SQUAD_UUID

    echo -e "   ${DIM}Запись конфигурации...${RESET}"
    sed -i "s~^BOT_TOKEN=.*~BOT_TOKEN=$BOT_TOKEN~" "$APP_DIR/.env"
    sed -i "s~^ADMIN_ID=.*~ADMIN_ID=$ADMIN_ID~" "$APP_DIR/.env"
    sed -i "s~^ACCESS_CODE=.*~ACCESS_CODE=$ACCESS_CODE~" "$APP_DIR/.env"
    sed -i "s~^REMNAWAVE_BASE_URL=.*~REMNAWAVE_BASE_URL=$REMNAWAVE_BASE_URL~" "$APP_DIR/.env"
    sed -i "s~^REMNAWAVE_TOKEN=.*~REMNAWAVE_TOKEN=$REMNAWAVE_TOKEN~" "$APP_DIR/.env"
    sed -i "s~^REMNAWAVE_DEFAULT_SQUAD_UUID=.*~REMNAWAVE_DEFAULT_SQUAD_UUID=$REMNAWAVE_DEFAULT_SQUAD_UUID~" "$APP_DIR/.env"

    info "Создание системной службы (systemd)..."
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
    systemctl enable $SERVICE_NAME >/dev/null 2>&1
    systemctl start $SERVICE_NAME

    if [ "$(realpath "$0")" != "$SCRIPT_PATH" ]; then
        cp "$0" "$SCRIPT_PATH"
        chmod +x "$SCRIPT_PATH"
    fi

    echo ""
    success "ПРОЦЕСС УСТАНОВКИ УСПЕШНО ЗАВЕРШЕН!"
    echo -e "Вызывайте панель управления из любой точки системы командой: ${CYAN}${BOLD}remnabot${RESET}"
    echo ""
    read -n 1 -s -r -p "Нажмите любую клавишу для продолжения..."
}

# ==============================================================================
# ОБНОВЛЕНИЕ БОТА
# ==============================================================================

update_bot() {
    draw_banner
    if [ ! -d "$APP_DIR" ]; then
        error "Бот не установлен! Сначала выполните установку."
        sleep 2
        return
    fi

    echo -e "${CYAN}╭────────────────────────────────────────────────────╮${RESET}"
    echo -e "${CYAN}│${RESET} Выберите вариант обновления:                       ${CYAN}│${RESET}"
    echo -e "${CYAN}│${RESET}  1) 📦 Сохранить текущий .env (Рекомендуется)      ${CYAN}│${RESET}"
    echo -e "${CYAN}│${RESET}  2) 🆕 Обновить .env (создать новый шаблон)        ${CYAN}│${RESET}"
    echo -e "${CYAN}│${RESET}  0) 🔙 Отмена                                      ${CYAN}│${RESET}"
    echo -e "${CYAN}╰────────────────────────────────────────────────────╯\n${RESET}"
    read -r -p " Выберите действие [0-2]: " up_act

    if [[ "$up_act" == "0" ]]; then return; fi
    if [[ "$up_act" != "1" && "$up_act" != "2" ]]; then warn "Неверный ввод."; sleep 1; return; fi

    info "Остановка службы..."
    systemctl stop $SERVICE_NAME

    info "Резервное копирование текущего .env..."
    cp "$APP_DIR/.env" "$APP_DIR/.env.backup"

    info "Получение обновлений из GitHub..."
    cd "$APP_DIR" || exit
    git fetch --all >/dev/null 2>&1
    local branch=$(git rev-parse --abbrev-ref HEAD)
    git reset --hard origin/$branch >/dev/null 2>&1
    
    sed -i '/^logging/d' "$APP_DIR/requirements.txt"

    info "Обновление зависимостей Python..."
    source "$APP_DIR/venv/bin/activate"
    pip install -q -r "$APP_DIR/requirements.txt"

    if [[ "$up_act" == "1" ]]; then
        info "Восстановление старого .env файла..."
        cp "$APP_DIR/.env.backup" "$APP_DIR/.env"
    elif [[ "$up_act" == "2" ]]; then
        info "Сброс .env файла на новый шаблон..."
        if [ -f "$APP_DIR/.env.example" ]; then
            cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        fi
        echo -e "   ${DIM}Ваш старый конфигурационный файл сохранен как .env.backup${RESET}"
        sleep 2
        nano "$APP_DIR/.env"
    fi

    info "Запуск службы..."
    systemctl start $SERVICE_NAME
    success "Бот успешно обновлен до последней версии!"
    sleep 2
}

# ==============================================================================
# ПРОСМОТР ЛОГОВ
# ==============================================================================

show_logs() {
    while true; do
        draw_banner
        echo -e "${CYAN}╭────────────────────────────────────────────────────╮${RESET}"
        echo -e "${CYAN}│${RESET}  1) 🟢 Live логи (в реальном времени)              ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  2) 📄 Подробные логи (последние 500 строк)        ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  0) 🔙 Назад в меню                                ${CYAN}│${RESET}"
        echo -e "${CYAN}╰────────────────────────────────────────────────────╯\n${RESET}"
        read -r -p " Выберите действие [0-2]: " log_act

        case "$log_act" in
            1) 
                info "Запуск Live-логов. Для выхода нажмите Ctrl+C"
                sleep 2
                journalctl -u $SERVICE_NAME -f
                ;;
            2) 
                info "Открываю последние 500 строк (для выхода из логов нажмите 'q')"
                sleep 2
                journalctl -u $SERVICE_NAME -n 500 --no-pager | less
                ;;
            0) return ;;
            *) warn "Неверный ввод."; sleep 1 ;;
        esac
    done
}

# ==============================================================================
# ДАШБОРД (СТАТУС)
# ==============================================================================

show_info() {
    draw_banner
    info "Сбор информации о статусе бота..."
    
    local status_systemd=$(systemctl is-active $SERVICE_NAME 2>/dev/null)
    local is_installed=$([ -d "$APP_DIR" ] && echo "ДА" || echo "НЕТ")
    local txt_bot=$([[ "$status_systemd" == "active" ]] && echo "РАБОТАЕТ" || echo "ОСТАНОВЛЕН")
    local clr_bot=$([[ "$status_systemd" == "active" ]] && echo "$GREEN" || echo "$RED")
    
    local bot_token=$(grep "^BOT_TOKEN=" "$APP_DIR/.env" 2>/dev/null | cut -d'=' -f2 | cut -c 1-15)
    [[ -n "$bot_token" ]] && bot_token="${bot_token}..." || bot_token="Не настроен"

    local admin_id=$(grep "^ADMIN_ID=" "$APP_DIR/.env" 2>/dev/null | cut -d'=' -f2)
    [[ -z "$admin_id" ]] && admin_id="Не настроен"

    # Математика для точного выравнивания правой границы (строго 52 символа)
    local pad_1=$((31 - ${#txt_bot}))
    local pad_2=$((31 - ${#is_installed}))
    local pad_3=$((31 - ${#bot_token}))
    local pad_4=$((31 - ${#admin_id}))

    clear
    draw_banner
    echo -e "${CYAN}╭────────────────────────────────────────────────────╮${RESET}"
    printf "${CYAN}│${RESET} 🤖 Бот:            ${BOLD}%s${RESET}%*s ${CYAN}│${RESET}\n" "$is_installed" "$pad_2" ""
    printf "${CYAN}│${RESET} 📦 Служба:         %s%s${RESET}%*s ${CYAN}│${RESET}\n" "$clr_bot" "$txt_bot" "$pad_1" ""
    printf "${CYAN}│${RESET} 🔑 Токен:          ${DIM}%s${RESET}%*s ${CYAN}│${RESET}\n" "$bot_token" "$pad_3" ""
    printf "${CYAN}│${RESET} 👤 Admin ID:       ${DIM}%s${RESET}%*s ${CYAN}│${RESET}\n" "$admin_id" "$pad_4" ""
    echo -e "${CYAN}╰────────────────────────────────────────────────────╯${RESET}"
    
    echo ""
    read -n 1 -s -r -p "Нажмите любую клавишу для возврата в меню..."
}

# ==============================================================================
# УПРАВЛЕНИЕ СЛУЖБОЙ
# ==============================================================================

manage_service() {
    local action=$1
    local action_ru=$2
    draw_banner
    if [ ! -d "$APP_DIR" ]; then
        error "Бот не установлен!"
        sleep 1.5
        return
    fi
    info "Выполняется $action_ru..."
    systemctl "$action" $SERVICE_NAME
    success "Служба успешно обработала команду."
    sleep 1.5
}

edit_env() {
    draw_banner
    if [ -f "$APP_DIR/.env" ]; then
        nano "$APP_DIR/.env"
        echo ""
        read -r -p " Конфигурация изменена. Перезапустить бота? (y/n): " ans
        if [[ "$ans" =~ ^[Yy]$ ]]; then
            systemctl restart $SERVICE_NAME
            success "Бот перезапущен с новыми настройками."
            sleep 1.5
        fi
    else
        error "Файл .env не найден. Установите бота сначала."
        sleep 1.5
    fi
}

# ==============================================================================
# ПОЛНОЕ УДАЛЕНИЕ
# ==============================================================================

uninstall_all() {
    draw_banner
    echo -e "${RED}${BOLD}⚠️  ВНИМАНИЕ: АБСОЛЮТНОЕ УДАЛЕНИЕ БОТА ⚠️${RESET}"
    echo -e "${DIM}Будут безвозвратно удалены следующие компоненты:${RESET}"
    echo -e "  ${RED}1.${RESET} Системная служба ($SERVICE_NAME)"
    echo -e "  ${RED}2.${RESET} Рабочая директория бота ($APP_DIR)"
    echo -e "  ${RED}3.${RESET} Алиас и команда вызова ($SCRIPT_PATH)\n"
    
    read -r -p "Вы абсолютно уверены, что хотите удалить бота? (y/n): " confirm
    if [[ "$confirm" != "y" ]]; then warn "Процесс удаления отменен."; sleep 1.5; return; fi

    info "Запущен процесс полной очистки..."
    
    systemctl stop $SERVICE_NAME >/dev/null 2>&1
    systemctl disable $SERVICE_NAME >/dev/null 2>&1
    rm -f /etc/systemd/system/$SERVICE_NAME
    systemctl daemon-reload
    
    rm -rf "$APP_DIR"
    rm -f "$SCRIPT_PATH"
    
    success "Система очищена. Бот удален."
    exit 0
}

# ==============================================================================
# ГЛАВНОЕ МЕНЮ (МАРШРУТИЗАЦИЯ)
# ==============================================================================

main_menu() {
    while true; do
        draw_banner
        echo -e "${CYAN}╭────────────────────────────────────────────────────╮${RESET}"
        echo -e "${CYAN}│${RESET}  1) 🚀 Установить бота                             ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  2) 🔄 Обновить бота (из GitHub)                 ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  3) 🟢 Запустить (Start)                           ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  4) 🔴 Остановить (Stop)                           ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  5) 🔄 Перезапустить (Restart)                     ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  6) 📊 Статус (Dashboard)                          ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  7) 📋 Логи бота                                   ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  8) 🔧 Редактировать .env                          ${CYAN}│${RESET}"
        echo -e "${CYAN}├────────────────────────────────────────────────────┤${RESET}"
        echo -e "${CYAN}│${RESET}  9) ${RED}🧨 Удалить бота${RESET}                                ${CYAN}│${RESET}"
        echo -e "${CYAN}│${RESET}  0) 🚪 Выход                                       ${CYAN}│${RESET}"
        echo -e "${CYAN}╰────────────────────────────────────────────────────╯\n${RESET}"
        read -r -p " Выберите действие [0-9]: " act

        case "$act" in
            1) install_bot ;;
            2) update_bot ;;
            3) manage_service start "запуск службы" ;;
            4) manage_service stop "остановка службы" ;;
            5) manage_service restart "перезапуск службы" ;;
            6) show_info ;;
            7) show_logs ;;
            8) edit_env ;;
            9) uninstall_all ;;
            0) clear; exit 0 ;;
            *) warn "Неверный ввод, выберите пункт от 0 до 9."; sleep 1 ;;
        esac
    done
}

# ==============================================================================
# ТОЧКА ВХОДА
# ==============================================================================

if [[ "$EUID" -ne 0 ]]; then 
    echo -e "${RED}✖ Ошибка: Этот скрипт требует привилегий суперпользователя (root). Запустите через sudo.${RESET}"
    exit 1
fi

main_menu
