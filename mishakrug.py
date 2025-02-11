import os
import pytz
from datetime import datetime, time
from dotenv import load_dotenv
import logging
from pathlib import Path
from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue
)
from telegram.error import TelegramError, BadRequest

# Загрузка переменных окружения
load_dotenv()

# Получение токена из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Получение списка ID администраторов
ADMIN_CHAT_IDS = set(int(admin_id.strip()) for admin_id in os.getenv('ADMIN_CHAT_ID').split(','))

# Московское время
moscow_tz = pytz.timezone('Europe/Moscow')

async def start_concert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запуск концерта вручную (только для администратора)"""
    if update.effective_user.id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Только администратор может запускать концерт!")
        return

    chat_id = update.effective_chat.id
    
    # Установка разрешений для чата (разрешаем только видеокружочки)
    permissions = ChatPermissions(
        can_send_messages=False, 
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_send_polls=False,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_send_photos=False,
        can_send_videos=False, 
        can_send_audios=False,
        can_send_documents=False,
        can_send_video_notes=True,  # Разрешаем только видеокружочки
        can_send_voice_notes=False
    )
    
    try:
        # Проверяем права бота в чате
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not bot_member.can_restrict_members:
            await update.message.reply_text("❌ Ошибка: У меня нет прав администратора в этом чате.\n"
                                          "Пожалуйста, назначьте меня администратором с правами:\n"
                                          "- Удаление сообщений\n"
                                          "- Блокировка участников\n"
                                          "- Управление правами участников")
            return

        # Пробуем установить разрешения
        try:
            await context.bot.set_chat_permissions(chat_id, permissions)
            msg = await update.message.reply_text("Я включаю Михаила Круга")
            
            # Пробуем удалить командное сообщение
            try:
                await update.message.delete()
            except BadRequest as e:
                if "Message can't be deleted" in str(e):
                    await msg.edit_text(msg.text + "\n\n⚠️ Не удалось удалить команду: нет прав на удаление сообщений")
                else:
                    raise e
                    
        except BadRequest as e:
            if "Not enough rights" in str(e):
                await update.message.reply_text("❌ Ошибка: Не удалось изменить права участников.\n"
                                              "Убедитесь, что у меня есть права:\n"
                                              "- Управление правами участников")
            else:
                await update.message.reply_text(f"❌ Ошибка при запуске концерта: {str(e)}")
                
    except TelegramError as e:
        await update.message.reply_text(f"❌ Произошла ошибка Telegram: {str(e)}\n"
                                      "Пожалуйста, проверьте права бота и попробуйте снова.")

async def stop_concert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Остановка концерта вручную (только для администратора)"""
    if update.effective_user.id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Только администратор может останавливать концерт!")
        return

    chat_id = update.effective_chat.id
    
    # Восстановление всех прав
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_send_polls=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_send_photos=True,
        can_send_videos=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_video_notes=True,
        can_send_voice_notes=True
    )
    
    try:
        # Проверяем права бота в чате
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if not bot_member.can_restrict_members:
            await update.message.reply_text("❌ Ошибка: У меня нет прав администратора в этом чате.\n"
                                          "Пожалуйста, назначьте меня администратором с правами:\n"
                                          "- Удаление сообщений\n"
                                          "- Блокировка участников\n"
                                          "- Управление правами участников")
            return

        # Пробуем установить разрешения
        try:
            await context.bot.set_chat_permissions(chat_id, permissions)
            msg = await update.message.reply_text("Концерт Михаила Круга окончен, мемасы снова доступны")
            
            # Пробуем удалить командное сообщение
            try:
                await update.message.delete()
            except BadRequest as e:
                if "Message can't be deleted" in str(e):
                    await msg.edit_text(msg.text + "\n\n⚠️ Не удалось удалить команду: нет прав на удаление сообщений")
                else:
                    raise e
                    
        except BadRequest as e:
            if "Not enough rights" in str(e):
                await update.message.reply_text("❌ Ошибка: Не удалось изменить права участников.\n"
                                              "Убедитесь, что у меня есть права:\n"
                                              "- Управление правами участников")
            else:
                await update.message.reply_text(f"❌ Ошибка при остановке концерта: {str(e)}")
                
    except TelegramError as e:
        await update.message.reply_text(f"❌ Произошла ошибка Telegram: {str(e)}\n"
                                      "Пожалуйста, проверьте права бота и попробуйте снова.")

async def check_schedule(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка расписания для автоматического запуска/остановки концерта"""
    try:
        now = datetime.now(moscow_tz)
        
        # Получаем все чаты из контекста бота
        managed_chats = context.bot_data.get('managed_chats', set())
        
        if not managed_chats:
            return  # Нет зарегистрированных чатов
            
        print(f"[{now}] Проверка расписания. Зарегистрированные чаты: {managed_chats}")
        
        for chat_id in managed_chats:
            try:
                # Запуск концерта по понедельникам в 8:00
                if now.weekday() == 0 and now.hour == 8 and now.minute == 0:
                    # Удаляем лог-файл перед запуском концерта
                    log_file = Path(os.path.dirname(os.path.abspath(__file__))) / 'mishakrug.log'
                    if log_file.exists():
                        try:
                            log_file.unlink()
                            print(f"[{now}] Лог-файл успешно удален")
                        except Exception as log_error:
                            print(f"[{now}] Ошибка при удалении лог-файла: {log_error}")
                    # Разрешаем только видеокружочки
                    permissions = ChatPermissions(
                        can_send_messages=False, 
                        can_send_other_messages=False,
                        can_add_web_page_previews=False,
                        can_send_polls=False,
                        can_change_info=False,
                        can_invite_users=True,
                        can_pin_messages=False,
                        can_send_photos=False,
                        can_send_videos=False, 
                        can_send_audios=False,
                        can_send_documents=False,
                        can_send_video_notes=True,  # Разрешаем только видеокружочки
                        can_send_voice_notes=False
                    )
                    await context.bot.set_chat_permissions(chat_id, permissions)
                    msg = await context.bot.send_message(chat_id, "Я включаю Михаила Круга")
                    print(f"[{now}] Запущен концерт в чате {chat_id}")
                    await msg.delete()
                    
                # Остановка концерта каждый день в 23:59
                elif now.hour == 23 and now.minute == 59:
                    # Восстанавливаем все права
                    permissions = ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_send_polls=True,
                        can_change_info=False,
                        can_invite_users=True,
                        can_pin_messages=False,
                        can_send_photos=True,
                        can_send_videos=True,
                        can_send_audios=True,
                        can_send_documents=True,
                        can_send_video_notes=True,
                        can_send_voice_notes=True
                    )
                    await context.bot.set_chat_permissions(chat_id, permissions)
                    msg = await context.bot.send_message(chat_id, "Концерт Михаила Круга окончен, мемасы снова доступны")
                    print(f"[{now}] Остановлен концерт в чате {chat_id}")
                    await msg.delete()
                    
            except Exception as chat_error:
                print(f"[{now}] Ошибка при обработке чата {chat_id}: {chat_error}")
                # Отправляем сообщение об ошибке администратору
                # Отправляем сообщение об ошибке всем администраторам
                for admin_id in ADMIN_CHAT_IDS:
                    try:
                        error_msg = await context.bot.send_message(
                            admin_id,
                            f"Ошибка при обработке чата {chat_id}:\n{str(chat_error)}"
                        )
                        await error_msg.delete()
                    except Exception as admin_msg_error:
                        print(f"[{now}] Не удалось отправить сообщение администратору {admin_id}: {admin_msg_error}")
                    
    except Exception as e:
        print(f"[{now}] Глобальная ошибка в check_schedule: {e}")
        # Отправляем сообщение об ошибке всем администраторам
        for admin_id in ADMIN_CHAT_IDS:
            try:
                error_msg = await context.bot.send_message(
                    admin_id,
                    f"Глобальная ошибка в check_schedule:\n{str(e)}"
                )
                await error_msg.delete()
            except Exception as admin_msg_error:
                print(f"[{now}] Не удалось отправить сообщение администратору {admin_id}: {admin_msg_error}")

async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Регистрация чата для управления концертами"""
    if update.effective_user.id not in ADMIN_CHAT_IDS:
        await update.message.reply_text("Только администратор может регистрировать чаты!")
        return
        
    chat_id = update.effective_chat.id
    if 'managed_chats' not in context.bot_data:
        context.bot_data['managed_chats'] = set()
    
    context.bot_data['managed_chats'].add(chat_id)
    await update.message.reply_text("Чат зарегистрирован для управления концертами!")

async def unregister_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отмена регистрации чата"""
    if update.effective_user.id not in ADMIN_CHAT_IDS:
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
    # Настройка логирования
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logger = logging.getLogger(__name__)

    try:
        # Создание приложения с явным указанием использования job_queue
        application = (
            Application.builder()
            .token(TOKEN)
            .concurrent_updates(True)  # Включаем параллельную обработку обновлений
            .job_queue(JobQueue())  # Явно включаем поддержку job_queue
            .build()
        )

        # Добавление обработчиков команд
        application.add_handler(CommandHandler("start_concert", start_concert))
        application.add_handler(CommandHandler("stop_concert", stop_concert))
        application.add_handler(CommandHandler("register_chat", register_chat))
        application.add_handler(CommandHandler("unregister_chat", unregister_chat))

        # Настройка планировщика задач для проверки каждую минуту
        job_queue = application.job_queue
        if job_queue:
            job_queue.run_repeating(
                check_schedule,
                interval=60,
                first=1  # Начать первую проверку через 1 секунду после запуска
            )
            logger.info("Планировщик задач успешно настроен")
        else:
            logger.error("Не удалось инициализировать планировщик задач!")
            return

        # Запуск бота с выводом информации о запуске
        logger.info("Бот запущен и готов к работе!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == '__main__':
    main()
