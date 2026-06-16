#!/bin/bash

# Форсируем UTF-8 для корректного отображения кириллицы в nano и логах
export LC_ALL=C.UTF-8
export LANG=C.UTF-8
export LANGUAGE=C.UTF-8

# ==============================================================================
# REMNO APPROVE BOT MANAGER
# Автоматизированный скрипт для управления ботом
# ==============================================================================

# --- КОНФИГУРАЦИЯ И СИСТЕМНЫЕ ПУТИ ---
APP_DIR="/opt/remno-approvebot"
BACKUP_DIR="/opt/remno-approvebot-backups"
AUTOBACKUP_CONF="/opt/remno-approvebot/.autobackup"
AUTOBACKUP_SCRIPT="/usr/local/bin/remnabot-autobackup.sh"
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
    echo -e "${MAGENTA}${BOLD}╭───────────────────────────────────────────────────╮"
    echo -e "│             R E M N O   A P P R O V E             │"
    echo -e "│                   Bot Manager                     │"
    echo -e "╰───────────────────────────────────────────────────╯${RESET}"
}

# ==============================================================================
# СИСТЕМНЫЕ ФУНКЦИИ И УТИЛИТЫ
# ==============================================================================

check_deps() {
    info "Проверка и установка системных зависимостей"
    export DEBIAN_FRONTEND=noninteractive
    
    local msg="Обновление списка пакетов (apt update)..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    if out=$(apt-get update 2>&1); then
        echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"
    else
        echo -e "\r   ${RED}✖${RESET} ${DIM}${msg}${RESET}"
        error "Не удалось обновить список пакетов Ubuntu/Debian."
        echo -e "${DIM}Детали ошибки:\n$out${RESET}"
        exit 1
    fi
    
    local deps=(git python3 python3-venv python3-pip curl nano cron zip unzip)
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null && ! dpkg -l | grep -q "^ii  $dep "; then
            msg="Установка пакета: $dep..."
            echo -n -e "   ${DIM}► ${msg}${RESET}"
            if out=$(apt-get install -yq "$dep" 2>&1); then
                echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"
            else
                echo -e "\r   ${RED}✖${RESET} ${DIM}${msg}${RESET}"
                error "Произошла ошибка при установке системного пакета: $dep"
                echo -e "${DIM}Детали ошибки:\n$out${RESET}"
                exit 1
            fi
        fi
    done
    
    msg="Настройка службы cron..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    systemctl enable cron >/dev/null 2>&1
    systemctl start cron >/dev/null 2>&1
    echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"
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

    info "Загрузка исходного кода бота"
    local msg="Клонирование репозитория GitHub..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    if out=$(git clone -q "$REPO_URL" "$APP_DIR" 2>&1); then
        echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"
    else
        echo -e "\r   ${RED}✖${RESET} ${DIM}${msg}${RESET}"
        error "Не удалось клонировать репозиторий с GitHub."
        echo -e "${DIM}Детали ошибки:\n$out${RESET}"
        exit 1
    fi
    
    msg="Применение системных фиксов (logging)..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    sed -i '/^logging/d' "$APP_DIR/requirements.txt"
    echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"
    
    info "Настройка Python окружения"
    msg="Создание виртуального окружения (venv)..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    if out=$(python3 -m venv "$APP_DIR/venv" 2>&1); then
        echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"
    else
        echo -e "\r   ${RED}✖${RESET} ${DIM}${msg}${RESET}"
        error "Не удалось создать виртуальное окружение Python."
        echo -e "${DIM}Детали ошибки:\n$out${RESET}"
        exit 1
    fi
    
    source "$APP_DIR/venv/bin/activate"
    
    msg="Установка зависимостей (pip install)..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    if out=$(pip install -q -r "$APP_DIR/requirements.txt" 2>&1); then
        echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"
    else
        echo -e "\r   ${RED}✖${RESET} ${DIM}${msg}${RESET}"
        error "Не удалось установить Python-зависимости (pip)."
        echo -e "${DIM}Детали ошибки:\n$out${RESET}"
        exit 1
    fi

    info "Настройка конфигурации"
    if [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        echo -e "   ${GREEN}✔${RESET} ${DIM}Создан базовый файл .env из шаблона${RESET}"
    else
        touch "$APP_DIR/.env"
        echo -e "   ${GREEN}✔${RESET} ${DIM}Создан пустой файл .env${RESET}"
    fi

    info "Финальная настройка системы"
    msg="Генерация службы systemd..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    cat > /etc/systemd/system/$SERVICE_NAME <<EOF
[Unit]
Description=Remno Approve Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python3 $APP_DIR/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"

    msg="Запуск службы бота..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    systemctl daemon-reload
    systemctl enable $SERVICE_NAME >/dev/null 2>&1
    if out=$(systemctl start $SERVICE_NAME 2>&1); then
        echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"
    else
        echo -e "\r   ${RED}✖${RESET} ${DIM}${msg}${RESET}"
        echo -e "   ${DIM}Служба создана, но не запустилась (нужно настроить .env)${RESET}"
    fi

    msg="Создание глобальных алиасов (симлинк)..."
    echo -n -e "   ${DIM}► ${msg}${RESET}"
    # Делаем скрипт в репозитории исполняемым и создаем симлинк на него
    chmod +x "$APP_DIR/remnabotscrypt.sh"
    ln -sf "$APP_DIR/remnabotscrypt.sh" "$SCRIPT_PATH"
    generate_autobackup_script
    echo -e "\r   ${GREEN}✔${RESET} ${DIM}${msg}${RESET}"

    echo ""
    success "ПРОЦЕСС УСТАНОВКИ УСПЕШНО ЗАВЕРШЕН!"
    echo -e " Вызывайте панель управления командой: ${CYAN}${BOLD}remnabot${RESET}"
    echo -e " ${DIM}Отредактируйте .env или восстановите бэкап через меню, если еще этого не сделали.${RESET}"
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

    echo -e " Выберите вариант обновления:"
    echo -e "  1)  📦 Сохранить текущий файл настроек (Рекомендуется)"
    echo -e "  2)  🆕 Обновить файл настроек (Сброс параметров)"
    echo -e "  0)  🔙 Отмена\n"
    read -r -p " Выберите действие [0-2]: " up_act

    if [[ "$up_act" == "0" ]]; then return; fi
    if [[ "$up_act" != "1" && "$up_act" != "2" ]]; then warn "Неверный ввод."; sleep 1; return; fi

    info "Создание бэкапа перед обновлением..."
    mkdir -p "$BACKUP_DIR"
    local bname="update_$(date +%Y-%m-%d_%H-%M-%S).zip"
    
    cd "$APP_DIR" || exit
    [ -f ".env" ] || [ -f "data/bot.db" ] && zip -q "$BACKUP_DIR/$bname" .env data/bot.db 2>/dev/null
    
    echo -e "   ${GREEN}✔${RESET} ${DIM}Сохранен бэкап: $BACKUP_DIR/$bname${RESET}"

    info "Остановка службы..."
    systemctl stop $SERVICE_NAME

    info "Резервное копирование временных данных..."
    cp "$APP_DIR/.env" "$APP_DIR/.env.backup"
    
    rm -rf "/tmp/remnabot_assets" "/tmp/remnabot_data"
    mkdir -p "/tmp/remnabot_assets" "/tmp/remnabot_data"
    
    if [ -d "$APP_DIR/assets" ]; then
        cp -a "$APP_DIR/assets/." "/tmp/remnabot_assets/" 2>/dev/null
    fi
    if [ -f "$APP_DIR/data/bot.db" ]; then
        cp "$APP_DIR/data/bot.db" "/tmp/remnabot_data/" 2>/dev/null
    fi

    info "Получение обновлений из GitHub..."
    cd "$APP_DIR" || exit
    git fetch --all >/dev/null 2>&1
    local branch=$(git rev-parse --abbrev-ref HEAD)
    git reset --hard origin/$branch >/dev/null 2>&1
    
    sed -i '/^logging/d' "$APP_DIR/requirements.txt"

    info "Обновление зависимостей Python..."
    source "$APP_DIR/venv/bin/activate"
    pip install -q -r "$APP_DIR/requirements.txt"

    info "Восстановление файлов БД и ресурсов..."
    if [ -d "/tmp/remnabot_assets" ]; then
        mkdir -p "$APP_DIR/assets"
        cp -a "/tmp/remnabot_assets/." "$APP_DIR/assets/" 2>/dev/null
    fi
    if [ -f "/tmp/remnabot_data/bot.db" ]; then
        mkdir -p "$APP_DIR/data"
        cp "/tmp/remnabot_data/bot.db" "$APP_DIR/data/" 2>/dev/null
    fi

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
    
    # Обновляем права и симлинк на случай, если git переписал их права доступа
    chmod +x "$APP_DIR/remnabotscrypt.sh"
    ln -sf "$APP_DIR/remnabotscrypt.sh" "$SCRIPT_PATH"
    generate_autobackup_script

    info "Запуск службы..."
    systemctl start $SERVICE_NAME
    success "Бот и панель управления успешно обновлены!"
    
    echo -e "${DIM}Перезапуск панели управления...${RESET}"
    sleep 2
    # Команда exec заменяет текущий процесс на новый обновленный скрипт
    exec "$SCRIPT_PATH"
}

# ==============================================================================
# БЭКАПЫ И ВОССТАНОВЛЕНИЕ
# ==============================================================================

generate_autobackup_script() {
    cat > "$AUTOBACKUP_SCRIPT" << 'EOF'
#!/bin/bash
APP_DIR="/opt/remno-approvebot"
BACKUP_DIR="/opt/remno-approvebot-backups"
AUTOBACKUP_CONF="/opt/remno-approvebot/.autobackup"

[ -f "$AUTOBACKUP_CONF" ] && source "$AUTOBACKUP_CONF"
[ "$AUTO_ENABLED" != "1" ] && exit 0

mkdir -p "$BACKUP_DIR"
BNAME="auto_$(date +%Y-%m-%d_%H-%M-%S).zip"

cd "$APP_DIR" || exit 0
[ -f ".env" ] || [ -f "data/bot.db" ] && zip -q "$BACKUP_DIR/$BNAME" .env data/bot.db 2>/dev/null

if [ "$AUTO_RETAIN" -gt 0 ]; then
    cd "$BACKUP_DIR" || exit 0
    ls -t auto_*.zip 2>/dev/null | tail -n +$((AUTO_RETAIN + 1)) | xargs -d '\n' -r rm -f
fi
EOF
    chmod +x "$AUTOBACKUP_SCRIPT"
}

update_cron() {
    [ -f "$AUTOBACKUP_CONF" ] && source "$AUTOBACKUP_CONF"
    crontab -l 2>/dev/null | grep -v 'remnabot-autobackup.sh' > /tmp/current_cron
    
    if [ "$AUTO_ENABLED" == "1" ]; then
        if [ "$AUTO_INTERVAL" -lt 24 ]; then
            echo "0 */$AUTO_INTERVAL * * * $AUTOBACKUP_SCRIPT" >> /tmp/current_cron
        elif [ "$AUTO_INTERVAL" -eq 24 ]; then
            echo "0 0 * * * $AUTOBACKUP_SCRIPT" >> /tmp/current_cron
        else
            local days=$((AUTO_INTERVAL / 24))
            echo "0 0 */$days * * $AUTOBACKUP_SCRIPT" >> /tmp/current_cron
        fi
    fi
    
    crontab /tmp/current_cron
    rm -f /tmp/current_cron
}

backup_menu() {
    while true; do
        draw_banner
        echo -e " ${DIM}📁 Путь к бэкапам: $BACKUP_DIR${RESET}\n"
        echo -e "  1)  💾 Принудительный ручной бэкап"
        echo -e "  2)  ⚙️ Настройка автобэкапа"
        echo -e "  3)  ♻️ Восстановление из бэкапа"
        echo -e "  0)  🔙 Назад в меню\n"
        read -r -p " Выберите действие [0-3]: " b_act

        case "$b_act" in
            1)
                if [ ! -d "$APP_DIR" ]; then
                    error "Бот не установлен! Сначала выполните установку."
                    sleep 1.5
                    continue
                fi
                info "Создание ручного бэкапа..."
                mkdir -p "$BACKUP_DIR"
                local bname="manual_$(date +%Y-%m-%d_%H-%M-%S).zip"
                
                cd "$APP_DIR" || continue
                [ -f ".env" ] || [ -f "data/bot.db" ] && zip -q "$BACKUP_DIR/$bname" .env data/bot.db 2>/dev/null
                
                success "Бэкап успешно сохранен в архив:"
                echo -e "${DIM}$BACKUP_DIR/$bname${RESET}"
                sleep 2.5
                ;;
            2)
                if [ ! -d "$APP_DIR" ]; then
                    error "Бот не установлен! Сначала выполните установку."
                    sleep 1.5
                    continue
                fi
                autobackup_menu
                ;;
            3)
                if [ ! -d "$APP_DIR" ]; then
                    error "Сначала установите бота через пункт 1 в главном меню!"
                    sleep 2
                    continue
                fi
                
                if ! ls "$BACKUP_DIR"/*.zip >/dev/null 2>&1; then
                    error "Архивы с бэкапами не найдены!"
                    sleep 2
                    continue
                fi

                echo ""
                cd "$BACKUP_DIR" || continue
                mapfile -t backups < <(ls -1t *.zip 2>/dev/null)
                cd - >/dev/null
                
                echo -e " Доступные бэкапы:"
                local i=1
                for b in "${backups[@]}"; do
                    echo -e "  $i) 📁 $b"
                    ((i++))
                done
                echo -e "  0) 🔙 Отмена\n"
                
                read -r -p " Выберите бэкап [0-${#backups[@]}]: " b_idx
                
                if [[ "$b_idx" == "0" ]]; then continue; fi
                if [[ ! "$b_idx" =~ ^[0-9]+$ ]] || [ "$b_idx" -lt 1 ] || [ "$b_idx" -gt "${#backups[@]}" ]; then
                    warn "Неверный выбор."
                    sleep 1.5
                    continue
                fi
                
                local selected_bname="${backups[$((b_idx-1))]}"
                local bpath="$BACKUP_DIR/$selected_bname"
                
                if ! unzip -l "$bpath" 2>/dev/null | grep -qE "\.env|bot\.db"; then
                    error "В выбранном архиве нет файлов .env или bot.db"
                    sleep 2
                    continue
                fi
                
                echo -e "\n Что именно вы хотите восстановить?"
                echo -e "  1)  📦 Всё (Базу данных и настройки)"
                echo -e "  2)  🔧 Только настройки (.env)"
                echo -e "  3)  🗄️ Только базу данных (bot.db)"
                echo -e "  0)  🔙 Отмена"
                read -r -p " Выберите действие [0-3]: " r_act

                if [[ "$r_act" == "0" ]]; then continue; fi

                info "Остановка бота и распаковка данных..."
                systemctl stop $SERVICE_NAME
                
                local tmp_extract="/tmp/remnabot_restore_$$"
                rm -rf "$tmp_extract"
                mkdir -p "$tmp_extract"
                unzip -q "$bpath" -d "$tmp_extract"
                
                case "$r_act" in
                    1)
                        [ -f "$tmp_extract/.env" ] && cp "$tmp_extract/.env" "$APP_DIR/.env"
                        if [ -f "$tmp_extract/data/bot.db" ]; then
                            mkdir -p "$APP_DIR/data"
                            cp "$tmp_extract/data/bot.db" "$APP_DIR/data/bot.db"
                        fi
                        ;;
                    2)
                        [ -f "$tmp_extract/.env" ] && cp "$tmp_extract/.env" "$APP_DIR/.env"
                        ;;
                    3)
                        if [ -f "$tmp_extract/data/bot.db" ]; then
                            mkdir -p "$APP_DIR/data"
                            cp "$tmp_extract/data/bot.db" "$APP_DIR/data/bot.db"
                        fi
                        ;;
                    *)
                        warn "Неверный выбор. Отмена."
                        rm -rf "$tmp_extract"
                        systemctl start $SERVICE_NAME
                        sleep 1.5
                        continue
                        ;;
                esac
                
                rm -rf "$tmp_extract"
                systemctl start $SERVICE_NAME
                success "Данные успешно восстановлены! Бот запущен."
                sleep 2
                ;;
            0) return ;;
            *) warn "Неверный ввод."; sleep 1 ;;
        esac
    done
}

autobackup_menu() {
    [ ! -f "$AUTOBACKUP_CONF" ] && echo -e "AUTO_ENABLED=0\nAUTO_RETAIN=10\nAUTO_INTERVAL=12" > "$AUTOBACKUP_CONF"
    
    while true; do
        source "$AUTOBACKUP_CONF"
        local status_text=$([ "$AUTO_ENABLED" == "1" ] && echo -e "${GREEN}ВКЛ${RESET}" || echo -e "${RED}ВЫКЛ${RESET}")
        
        draw_banner
        echo -e " ${DIM}📁 Путь к бэкапам: $BACKUP_DIR${RESET}\n"
        echo -e "  1)  🔄 Статус автобэкапа: $status_text"
        echo -e "  2)  🔢 Лимит хранимых версий (Сейчас: $AUTO_RETAIN)"
        echo -e "  3)  ⏱️ Интервал в часах (Сейчас: $AUTO_INTERVAL)"
        echo -e "  0)  🔙 Назад\n"
        read -r -p " Выберите действие [0-3]: " ab_act

        case "$ab_act" in
            1)
                local new_status=$([ "$AUTO_ENABLED" == "1" ] && echo "0" || echo "1")
                sed -i "s/^AUTO_ENABLED=.*/AUTO_ENABLED=$new_status/" "$AUTOBACKUP_CONF"
                update_cron
                ;;
            2)
                read -r -p " Введите количество хранимых бэкапов (от 1 до 50): " n_ret
                if [[ "$n_ret" =~ ^[0-9]+$ ]] && [ "$n_ret" -ge 1 ] && [ "$n_ret" -le 50 ]; then
                    sed -i "s/^AUTO_RETAIN=.*/AUTO_RETAIN=$n_ret/" "$AUTOBACKUP_CONF"
                else
                    warn "Нужно ввести число от 1 до 50!"
                    sleep 1.5
                fi
                ;;
            3)
                read -r -p " Введите интервал бэкапа в часах (от 1 до 168): " n_int
                if [[ "$n_int" =~ ^[0-9]+$ ]] && [ "$n_int" -ge 1 ] && [ "$n_int" -le 168 ]; then
                    sed -i "s/^AUTO_INTERVAL=.*/AUTO_INTERVAL=$n_int/" "$AUTOBACKUP_CONF"
                    update_cron
                else
                    warn "Нужно ввести число от 1 до 168!"
                    sleep 1.5
                fi
                ;;
            0) return ;;
            *) warn "Неверный ввод."; sleep 1 ;;
        esac
    done
}

# ==============================================================================
# ПРОСМОТР ЛОГОВ
# ==============================================================================

show_logs() {
    while true; do
        draw_banner
        echo -e "  1)  🟢 Live логи (в реальном времени)"
        echo -e "  2)  📄 Подробные логи (последние 500 строк)"
        echo -e "  0)  🔙 Назад в меню\n"
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
                journalctl -u $SERVICE_NAME -n 500 --no-pager | less -R
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

    clear
    draw_banner
    echo -e " 🤖 Бот установлен:   ${BOLD}${is_installed}${RESET}"
    echo -e " 📦 Статус службы:    ${clr_bot}${txt_bot}${RESET}"
    echo -e " 🔑 Токен:            ${DIM}${bot_token}${RESET}"
    echo -e " 👤 Admin ID:         ${DIM}${admin_id}${RESET}\n"

    echo -e " ${BOLD}📁 Пути для отладки:${RESET}"
    echo -e "  • Папка бота:       ${DIM}${APP_DIR}${RESET}"
    echo -e "  • Папка бэкапов:    ${DIM}${BACKUP_DIR}${RESET}"
    echo -e "  • Системная служба: ${DIM}/etc/systemd/system/${SERVICE_NAME}${RESET}"
    echo -e "  • Вирт. окружение:  ${DIM}${APP_DIR}/venv${RESET}"
    echo -e "  • Файл настроек:    ${DIM}${APP_DIR}/.env${RESET}"
    echo -e "  • База данных:      ${DIM}${APP_DIR}/data/bot.db${RESET}\n"
    
    read -n 1 -s -r -p "Нажмите любую клавишу для возврата в меню..."
}

# ==============================================================================
# УПРАВЛЕНИЕ СЛУЖБОЙ И НАСТРОЙКАМИ
# ==============================================================================

service_menu() {
    while true; do
        draw_banner
        echo -e "  1)  🟢 Запустить службу"
        echo -e "  2)  🔴 Остановить службу"
        echo -e "  3)  🔄 Перезапустить службу"
        echo -e "  0)  🔙 Назад в меню\n"
        read -r -p " Выберите действие [0-3]: " s_act

        case "$s_act" in
            1) manage_service start "запуск службы" ;;
            2) manage_service stop "остановка службы" ;;
            3) manage_service restart "перезапуск службы" ;;
            0) return ;;
            *) warn "Неверный ввод."; sleep 1 ;;
        esac
    done
}

manage_service() {
    local action=$1
    local action_ru=$2
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

env_menu() {
    while true; do
        draw_banner
        if [ ! -d "$APP_DIR" ]; then
            error "Бот не установлен! Сначала выполните установку."
            sleep 1.5
            return
        fi

        echo -e "  1)  📝 Настройки (nano)"
        echo -e "  2)  🔄 Сбросить настройки по умолчанию"
        echo -e "  0)  🔙 Назад в меню\n"
        read -r -p " Выберите действие [0-2]: " env_act

        case "$env_act" in
            1)
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
                    error "Файл .env не найден."
                    sleep 1.5
                fi
                ;;
            2)
                echo -e "\n${RED}${BOLD}⚠️  ВНИМАНИЕ: Текущие настройки будут полностью удалены!${RESET}"
                read -r -p " Вы уверены, что хотите сбросить .env по умолчанию? (y/n): " confirm
                if [[ "$confirm" =~ ^[Yy]$ ]]; then
                    if [ -f "$APP_DIR/.env.example" ]; then
                        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
                        success "Настройки успешно сброшены!"
                    else
                        error "Файл шаблона (.env.example) не найден!"
                    fi
                else
                    warn "Сброс отменен."
                fi
                sleep 1.5
                ;;
            0) return ;;
            *) warn "Неверный ввод."; sleep 1 ;;
        esac
    done
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
    echo -e "  ${RED}3.${RESET} Системные алиасы и скрипты (remnabot во всех директориях)"
    echo -e "  ${RED}4.${RESET} Задачи автобэкапа в cron"
    echo -e "  ${DIM}(Ваши бэкапы в папке $BACKUP_DIR удалены не будут)${RESET}\n"
    
    read -r -p "Вы абсолютно уверены, что хотите удалить бота? (y/n): " confirm
    if [[ "$confirm" != "y" ]]; then warn "Процесс удаления отменен."; sleep 1.5; return; fi

    info "Запущен процесс полной очистки..."
    
    # 1. Удаление задач из cron
    crontab -l 2>/dev/null | grep -v 'remnabot-autobackup.sh' | crontab -
    
    # 2. Остановка и удаление службы
    systemctl stop $SERVICE_NAME >/dev/null 2>&1
    systemctl disable $SERVICE_NAME >/dev/null 2>&1
    rm -f /etc/systemd/system/$SERVICE_NAME
    systemctl daemon-reload
    
    # 3. Удаление рабочих файлов бота
    rm -rf "$APP_DIR"
    
    # 4. Агрессивное удаление системных скриптов и алиасов из всех возможных путей
    rm -f "/usr/local/bin/remnabot" "/usr/bin/remnabot" "/bin/remnabot"
    rm -f "/usr/local/bin/remnabot-autobackup.sh" "/usr/bin/remnabot-autobackup.sh" "/bin/remnabot-autobackup.sh"
    rm -f "$SCRIPT_PATH" "$AUTOBACKUP_SCRIPT"
    
    success "Система полностью очищена. Бот и системные скрипты удалены."
    
    # Выходим из скрипта с очисткой кэша путей bash
    hash -r 2>/dev/null
    exit 0
}

# ==============================================================================
# ГЛАВНОЕ МЕНЮ (МАРШРУТИЗАЦИЯ)
# ==============================================================================

main_menu() {
    while true; do
        draw_banner
        echo -e "  1)  🚀 Установить бота"
        echo -e "  2)  🔄 Обновить бота (из GitHub)"
        echo -e "  3)  ⚙️ Управление службой"
        echo -e "  4)  📊 Информация"
        echo -e "  5)  📋 Логи"
        echo -e "  6)  🔧 Настройки (.env)"
        echo -e "  7)  💾 Бэкапы и восстановление"
        echo -e "  8)  🧨 ${RED}Удалить бота${RESET}"
        echo -e "  0)  🚪 Выход\n"
        read -r -p " Выберите действие [0-8]: " act

        case "$act" in
            1) install_bot ;;
            2) update_bot ;;
            3) service_menu ;;
            4) show_info ;;
            5) show_logs ;;
            6) env_menu ;;
            7) backup_menu ;;
            8) uninstall_all ;;
            0) clear; exit 0 ;;
            *) warn "Неверный ввод, выберите пункт от 0 до 8."; sleep 1 ;;
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
