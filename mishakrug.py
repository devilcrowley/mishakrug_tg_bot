import os
import pytz
from datetime import datetime, time
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Загрузка переменных окружения
load_dotenv()

# Получение токена и chat_id администратора из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))

# Московское время
moscow_tz = pytz.timezone('Europe/Moscow')

async def start_concert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запуск концерта вручную (только для администратора)"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Только администратор может запускать концерт!")
        return

    chat_id = update.effective_chat.id
    
    # Установка разрешений для чата
    permissions = {
        "can_send_messages": True,
        "can_send_media_messages": True,
        "can_send_other_messages": False,
        "can_add_web_page_previews": False,
        "can_send_polls": False,
        "can_change_info": False,
        "can_invite_users": True,
        "can_pin_messages": False,
        "can_send_photos": False,
        "can_send_videos": True,
        "can_send_audios": False,
        "can_send_documents": False,
        "can_send_video_notes": True,
        "can_send_voice_notes": False,
    }
    
    await context.bot.set_chat_permissions(chat_id, permissions)
    await update.message.reply_text("Я включаю Михаила Круга")

async def stop_concert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Остановка концерта вручную (только для администратора)"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Только администратор может останавливать концерт!")
        return

    chat_id = update.effective_chat.id
    
    # Восстановление всех прав
    permissions = {
        "can_send_messages": True,
        "can_send_media_messages": True,
        "can_send_other_messages": True,
        "can_add_web_page_previews": True,
        "can_send_polls": True,
        "can_change_info": False,
        "can_invite_users": True,
        "can_pin_messages": False,
        "can_send_photos": True,
        "can_send_videos": True,
        "can_send_audios": True,
        "can_send_documents": True,
        "can_send_video_notes": True,
        "can_send_voice_notes": True,
    }
    
    await context.bot.set_chat_permissions(chat_id, permissions)
    await update.message.reply_text("Концерт Михаила Круга окончен, мемасы снова доступны")

async def check_schedule(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка расписания для автоматического запуска/остановки концерта"""
    now = datetime.now(moscow_tz)
    
    # Получаем все чаты из контекста бота
    for chat_id in context.bot_data.get('managed_chats', set()):
        # Запуск концерта по понедельникам в 8:00
        if now.weekday() == 0 and now.hour == 8 and now.minute == 0:
            permissions = {
                "can_send_messages": True,
                "can_send_media_messages": True,
                "can_send_other_messages": False,
                "can_add_web_page_previews": False,
                "can_send_polls": False,
                "can_change_info": False,
                "can_invite_users": True,
                "can_pin_messages": False,
                "can_send_photos": False,
                "can_send_videos": True,
                "can_send_audios": False,
                "can_send_documents": False,
                "can_send_video_notes": True,
                "can_send_voice_notes": False,
            }
            await context.bot.set_chat_permissions(chat_id, permissions)
            await context.bot.send_message(chat_id, "Я включаю Михаила Круга")
            
        # Остановка концерта каждый день в 23:59
        elif now.hour == 23 and now.minute == 59:
            permissions = {
                "can_send_messages": True,
                "can_send_media_messages": True,
                "can_send_other_messages": True,
                "can_add_web_page_previews": True,
                "can_send_polls": True,
                "can_change_info": False,
                "can_invite_users": True,
                "can_pin_messages": False,
                "can_send_photos": True,
                "can_send_videos": True,
                "can_send_audios": True,
                "can_send_documents": True,
                "can_send_video_notes": True,
                "can_send_voice_notes": True,
            }
            await context.bot.set_chat_permissions(chat_id, permissions)
            await context.bot.send_message(chat_id, "Концерт Михаила Круга окончен, мемасы снова доступны")

async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Регистрация чата для управления концертами"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Только администратор может регистрировать чаты!")
        return
        
    chat_id = update.effective_chat.id
    if 'managed_chats' not in context.bot_data:
        context.bot_data['managed_chats'] = set()
    
    context.bot_data['managed_chats'].add(chat_id)
    await update.message.reply_text("Чат зарегистрирован для управления концертами!")

async def unregister_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отмена регистрации чата"""
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Только администратор может отменять регистрацию чатов!")
        return
        
    chat_id = update.effective_chat.id
    if 'managed_chats' in context.bot_data and chat_id in context.bot_data['managed_chats']:
        context.bot_data['managed_chats'].remove(chat_id)
        await update.message.reply_text("Регистрация чата отменена!")
    else:
        await update.message.reply_text("Этот чат не был зарегистрирован!")

def main() -> None:
    """Запуск бота"""
    # Создание приложения
    application = Application.builder().token(TOKEN).build()

    # Добавление обработчиков команд
    application.add_handler(CommandHandler("start_concert", start_concert))
    application.add_handler(CommandHandler("stop_concert", stop_concert))
    application.add_handler(CommandHandler("register_chat", register_chat))
    application.add_handler(CommandHandler("unregister_chat", unregister_chat))

    # Настройка планировщика задач
    job_queue = application.job_queue
    
    # Проверка расписания каждую минуту
    job_queue.run_repeating(check_schedule, interval=60)

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
