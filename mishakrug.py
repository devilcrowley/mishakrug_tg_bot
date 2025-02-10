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

# Функция для проверки админских прав
def check_admin_rights(context: CallbackContext, chat_id: int, user_id: int) -> bool:
    bot_member = context.bot.get_chat_member(chat_id, user_id)
    return bot_member.status in ['administrator', 'creator'] and bot_member.can_restrict_members

# Функция, которая будет вызываться при добавлении бота в чат
def on_bot_added(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    user_id = context.bot.get_me().id

    if not check_admin_rights(context, chat_id, user_id):
        update.message.reply_text("Тут Круг объявлен иноагентом, добавь админом по-братски, обойдем эти санкции, этапом из Твери, зла немерено")
    else:
        update.message.reply_text("Спасибо за доверие! Буду следить за порядком.")

# Функция для отправки сообщения и ограничения прав
def start_concert(context: CallbackContext):
    job = context.job
    chat_id = job.context

    context.bot.send_message(chat_id, "Я включаю Михаила Круга")
    
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

# Функция для завершения концерта
def end_concert(context: CallbackContext):
    job = context.job
    chat_id = job.context

    context.bot.send_message(chat_id, "Концерт Михаила Круга окончен, мемасы снова доступны")
    
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

    # Планировщик задач
    updater.job_queue.run_once(schedule_concerts, when=0)

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
