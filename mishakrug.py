import logging
from telegram import Update, ChatPermissions
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import datetime
import pytz
from dotenv import load_dotenv
import os

# Загрузка переменных окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальная переменная для хранения состояния концерта
concert_active = False

# Функция для проверки админских прав
def check_admin_rights(context: CallbackContext, chat_id: int, user_id: int) -> bool:
    bot_member = context.bot.get_chat_member(chat_id, user_id)
    return bot_member.status in ['administrator', 'creator'] and bot_member.can_restrict_members

# Функция для проверки, является ли пользователь администратором
def is_admin(chat_id: int) -> bool:
    admin_chat_id = int(os.getenv("ADMIN_CHAT_ID"))
    return chat_id == admin_chat_id

# Функция для запуска концерта
def start_concert_command(update: Update, context: CallbackContext):
    global concert_active
    chat_id = update.message.chat_id

    if not is_admin(chat_id):
        update.message.reply_text("Ты не админ, Миша, всё х**ня, давай по новой.")
        return

    if concert_active:
        update.message.reply_text("Концерт уже идет, Миша в деле!")
        return

    concert_active = True
    update.message.reply_text("Я включаю Михаила Круга")

    # Блокируем все типы сообщений, кроме видеосообщений
    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_media_messages=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
    )
    context.bot.set_chat_permissions(chat_id, permissions)

# Функция для остановки концерта
def stop_concert_command(update: Update, context: CallbackContext):
    global concert_active
    chat_id = update.message.chat_id

    if not is_admin(chat_id):
        update.message.reply_text("Ты не админ, Миша, всё х**ня, давай по новой.")
        return

    if not concert_active:
        update.message.reply_text("Концерт уже окончен, мемасы доступны.")
        return

    concert_active = False
    update.message.reply_text("Концерт Михаила Круга окончен, мемасы снова доступны")

    # Восстанавливаем все права
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=True,
        can_invite_users=True,
        can_pin_messages=True,
    )
    context.bot.set_chat_permissions(chat_id, permissions)

# Функция для планирования задач
def schedule_concerts(context: CallbackContext):
    # Получаем список всех чатов, где есть бот
    for chat_id in context.bot.get_updates():
        if check_admin_rights(context, chat_id, context.bot.get_me().id):
            # Планируем начало концерта на каждый понедельник в 8:00 по Москве
            context.job_queue.run_daily(start_concert, time=datetime.time(hour=8, minute=0, tzinfo=pytz.timezone('Europe/Moscow')), days=(0,), context=chat_id)
            
            # Планируем завершение концерта на каждый день в 23:59 по Москве
            context.job_queue.run_daily(end_concert, time=datetime.time(hour=23, minute=59, tzinfo=pytz.timezone('Europe/Moscow')), days=(0,), context=chat_id)

def main():
    # Загрузка токена из переменной окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("Токен бота не найден в файле .env")

    updater = Updater(token, use_context=True)

    dp = updater.dispatcher

    # Обработчик добавления бота в чат
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, on_bot_added))

    # Команды для ручного запуска и остановки концерта
    dp.add_handler(CommandHandler("start_concert", start_concert_command))
    dp.add_handler(CommandHandler("stop_concert", stop_concert_command))

    # Планировщик задач
    updater.job_queue.run_once(schedule_concerts, when=0)

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
