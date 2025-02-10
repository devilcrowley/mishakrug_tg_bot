# Telegram Bot: Концерты Михаила Круга 🎸

Этот Telegram-бот создан для управления "концертами" Михаила Круга в чатах. Бот может автоматически запускать и останавливать концерты по расписанию, а также позволяет администратору вручную управлять концертами. Во время концерта участники чата могут отправлять только видеосообщения (кружочки).

## 🚀 Основные функции

### Автоматические концерты:

- Каждый понедельник в 8:00 по Москве бот запускает концерт:
  - Отправляет сообщение: "Я включаю Михаила Круга"
  - Блокирует все типы сообщений, кроме видеосообщений

- Каждый день в 23:59 по Москве бот завершает концерт:
  - Отправляет сообщение: "Концерт Михаила Круга окончен, мемасы снова доступны"
  - Восстанавливает все права участников чата

### Ручное управление концертами:

- Администратор может вручную запустить концерт командой `/start_concert`
- Администратор может вручную остановить концерт командой `/stop_concert`

### Проверка прав администратора:

- Бот проверяет, что команды на запуск и остановку концерта отправляет администратор, чей chat_id указан в файле .env

### Автозапуск через cron:

- Если бот по какой-то причине остановится, cron автоматически запустит его снова

## 🛠 Установка и настройка

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/devilcrowley/mishakrug_tg_bot.git
cd /opt/mishakrug_tg_bot
```

### 2. Установите зависимости

Убедитесь, что у вас установлен Python 3.8 или выше. Затем установите необходимые зависимости:

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### 3. Создайте файл .env

Создайте файл .env в корневой директории проекта и добавьте туда следующие переменные:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ADMIN_CHAT_ID=your_admin_chat_id_here
```

- `TELEGRAM_BOT_TOKEN`: Токен вашего бота, полученный от BotFather
- `ADMIN_CHAT_ID`: Ваш chat_id (узнать его можно, отправив сообщение боту /start и посмотрев логи)

### 4. Запустите бота


# Запуск бота в фоне с записью логов

```
nohup python3 mishakrug.py > mishakrug.log 2>&1 &
```
# Посмотреть логи

```
tail -f mishakrug.log
```

# Если нужно остановить бота, найдите его PID и завершите процесс

```
ps aux | grep python3
kill <PID>
```

## 🖥 Запуск на удаленном сервере с Linux Ubuntu

### 1. Подключитесь к серверу

Используйте SSH для подключения к вашему серверу:

```bash
ssh root@55.55.55.55
```

### 2. Установите необходимые пакеты

Убедитесь, что на сервере установлены Python и Git:

```bash
sudo apt update
sudo apt install python3 python3-pip git
```

### 3. Клонируйте репозиторий

```bash
git clone https://github.com/devilcrowley/mishakrug_tg_bot.git
cd /opt/mishakrug_tg_bot
```

### 4. Установите зависимости

```bash
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

### 5. Настройте файл .env

Создайте файл .env и добавьте туда токен бота и chat_id администратора, как описано выше.

### 6. Запустите бота

# Запуск бота в фоне с записью логов

```
nohup python3 mishakrug.py > mishakrug.log 2>&1 &
```
# Посмотреть логи

```
tail -f mishakrug.log
```

# Если нужно остановить бота, найдите его PID и завершите процесс

```
ps aux | grep python3
kill <PID>
```

## 🔄 Обновление из удаленного репозитория

Если вы внесли изменения в репозиторий, обновите код на сервере:

```bash
cd /opt/mishakrug_tg_bot
git pull origin main
```

После этого перезапустите бота:

```bash
pkill -f "python3 mishakrug.py"
nohup python3 mishakrug.py > mishakrug.log 2>&1 &
```

## ⏰ Настройка cron для автозапуска

Чтобы бот автоматически запускался после перезагрузки сервера или в случае сбоя, настройте cron:

1. Создайте скрипт для проверки и запуска бота (check_bot.sh):

```bash
#!/bin/bash

if ! pgrep -f "python3 mishakrug.py"; then
    python3 /opt/mishakrug_tg_bot/mishakrug.py &
    echo "Бот запущен."
else
    echo "Бот уже работает."
fi
```

2. Сделайте скрипт исполняемым:

```bash
chmod +x /opt/mishakrug_tg_bot/check_bot.sh
```

3. Откройте crontab для редактирования:

```bash
crontab -e
```

4. Добавьте строку для проверки каждые 5 минут:

```bash
*/5 * * * * /opt/mishakrug_tg_bot/check_bot.sh >> /opt/mishakrug_tg_bot/cron.log 2>&1
```

5. Сохраните и закройте файл.

## 🛠 Команды бота

- `/start_concert` — Запустить концерт вручную (только для администратора)
- `/stop_concert` — Остановить концерт вручную (только для администратора)


## 🙏 Благодарности

Спасибо Михаилу Кругу за вдохновение! 🎶
