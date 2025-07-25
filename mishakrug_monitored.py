import os
import pytz
import asyncio
from datetime import datetime, time
from dotenv import load_dotenv
import logging
from pathlib import Path
from telegram import Update, ChatPermissions, ChatMemberAdministrator
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    JobQueue
)
from telegram.error import TelegramError, BadRequest

# Импорт модулей мониторинга
from monitoring import api_monitor, monitor_async_api_call
from metrics_server import start_metrics_server
from telegram_wrapper import wrap_context_bot, wrap_update_message

# Загрузка переменных окружения
load_dotenv()

# Получение настроек из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
MODE = os.getenv('MODE', 'secured').lower()  # По умолчанию используем secured режим
METRICS_PORT = int(os.getenv('METRICS_PORT', 8080))  # Порт для сервера метрик

# Получение списка ID администраторов (используется только в secured режиме)
ADMIN_CHAT_IDS = set(int(admin_id.strip()) for admin_id in os.getenv('ADMIN_CHAT_ID').split(',')) if MODE == 'secured' else set()

# Московское время
moscow_tz = pytz.timezone('Europe/Moscow')

async def is_user_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверка, является ли пользователь администратором чата"""
    try:
        context = wrap_context_bot(context)
        chat_member = await context.bot.get_chat_member(chat_id, user_id)
        return isinstance(chat_member, ChatMemberAdministrator) or chat_member.status == 'creator'
    except TelegramError as e:
        api_monitor.record_error(e, 'get_chat_member', chat_id, user_id)
        return False

async def start_concert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запуск концерта вручную (только для администратора)"""
    try:
        update = wrap_update_message(update)
        context = wrap_context_bot(context)
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        # Проверка прав в зависимости от режима
        if MODE == 'secured':
            if user_id not in ADMIN_CHAT_IDS:
                await update.message.reply_text("❌ Только администратор бота может запускать концерт!")
                return
        else:  # public mode
            if not await is_user_admin(chat_id, user_id, context):
                await update.message.reply_text("❌ Только администратор чата может запускать концерт!")
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
            if not isinstance(bot_member, ChatMemberAdministrator):
                await update.message.reply_text("❌ Ошибка: Я не являюсь администратором в этом чате.\n"
                                              "Пожалуйста, назначьте меня администратором с правами:\n"
                                              "- Удаление сообщений\n"
                                              "- Блокировка участников\n"
                                              "- Управление правами участников")
                return
                
            if not (bot_member.can_restrict_members and bot_member.can_delete_messages):
                missing_rights = []
                if not bot_member.can_restrict_members:
                    missing_rights.append("- Управление правами участников")
                if not bot_member.can_delete_messages:
                    missing_rights.append("- Удаление сообщений")
                    
                await update.message.reply_text("❌ Ошибка: У меня недостаточно прав администратора.\n"
                                              "Необходимые права:\n" + "\n".join(missing_rights))
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
                        api_monitor.record_error(e, 'delete_message', chat_id, user_id)
                        raise e
                        
            except BadRequest as e:
                api_monitor.record_error(e, 'set_chat_permissions', chat_id, user_id)
                if "Not enough rights" in str(e):
                    await update.message.reply_text("❌ Ошибка: Не удалось изменить права участников.\n"
                                                  "Убедитесь, что у меня есть права:\n"
                                                  "- Управление правами участников")
                else:
                    await update.message.reply_text(f"❌ Ошибка при запуске концерта: {str(e)}")
                    
        except TelegramError as e:
            api_monitor.record_error(e, 'start_concert', chat_id, user_id)
            await update.message.reply_text(f"❌ Произошла ошибка Telegram: {str(e)}\n"
                                          "Пожалуйста, проверьте права бота и попробуйте снова.")
    except Exception as e:
        api_monitor.record_error(e, 'start_concert', chat_id if 'chat_id' in locals() else None, user_id if 'user_id' in locals() else None)
        logging.error(f"Неожиданная ошибка в start_concert: {e}")

async def stop_concert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Остановка концерта вручную (только для администратора)"""
    try:
        update = wrap_update_message(update)
        context = wrap_context_bot(context)
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        # Проверка прав в зависимости от режима
        if MODE == 'secured':
            if user_id not in ADMIN_CHAT_IDS:
                await update.message.reply_text("❌ Только администратор бота может останавливать концерт!")
                return
        else:  # public mode
            if not await is_user_admin(chat_id, user_id, context):
                await update.message.reply_text("❌ Только администратор чата может останавливать концерт!")
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
            if not isinstance(bot_member, ChatMemberAdministrator):
                await update.message.reply_text("❌ Ошибка: Я не являюсь администратором в этом чате.\n"
                                              "Пожалуйста, назначьте меня администратором с правами:\n"
                                              "- Удаление сообщений\n"
                                              "- Блокировка участников\n"
                                              "- Управление правами участников")
                return
                
            if not (bot_member.can_restrict_members and bot_member.can_delete_messages):
                missing_rights = []
                if not bot_member.can_restrict_members:
                    missing_rights.append("- Управление правами участников")
                if not bot_member.can_delete_messages:
                    missing_rights.append("- Удаление сообщений")
                    
                await update.message.reply_text("❌ Ошибка: У меня недостаточно прав администратора.\n"
                                              "Необходимые права:\n" + "\n".join(missing_rights))
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
                        api_monitor.record_error(e, 'delete_message', chat_id, user_id)
                        raise e
                        
            except BadRequest as e:
                api_monitor.record_error(e, 'set_chat_permissions', chat_id, user_id)
                if "Not enough rights" in str(e):
                    await update.message.reply_text("❌ Ошибка: Не удалось изменить права участников.\n"
                                                  "Убедитесь, что у меня есть права:\n"
                                                  "- Управление правами участников")
                else:
                    await update.message.reply_text(f"❌ Ошибка при остановке концерта: {str(e)}")
                    
        except TelegramError as e:
            api_monitor.record_error(e, 'stop_concert', chat_id, user_id)
            await update.message.reply_text(f"❌ Произошла ошибка Telegram: {str(e)}\n"
                                          "Пожалуйста, проверьте права бота и попробуйте снова.")
    except Exception as e:
        api_monitor.record_error(e, 'stop_concert', chat_id if 'chat_id' in locals() else None, user_id if 'user_id' in locals() else None)
        logging.error(f"Неожиданная ошибка в stop_concert: {e}")

async def start_concert_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запуск концерта по расписанию (понедельник 8:00 МСК)"""
    now = datetime.now(moscow_tz)
    logger = logging.getLogger(__name__)
    logger.info(f"[{now}] Запуск планового концерта")
    
    try:
        context = wrap_context_bot(context)
        
        # Получаем список активных чатов
        managed_chats = await get_managed_chats(context)
        logger.info(f"[{now}] Активные чаты для запуска концерта: {managed_chats}")
        
        if not managed_chats:
            logger.warning(f"[{now}] Нет активных чатов для запуска концерта")
            return
            
        for chat_id in managed_chats:
            try:
                # Проверяем права бота перед запуском
                bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                if not (isinstance(bot_member, ChatMemberAdministrator) and bot_member.can_restrict_members):
                    logger.error(f"[{now}] Недостаточно прав для запуска концерта в чате {chat_id}")
                    continue
                
                # Удаляем лог-файл перед запуском концерта
                log_file = Path(os.path.dirname(os.path.abspath(__file__))) / 'mishakrug.log'
                if log_file.exists():
                    try:
                        log_file.unlink()
                        logger.info(f"[{now}] Лог-файл успешно удален")
                    except Exception as log_error:
                        logger.error(f"[{now}] Ошибка при удалении лог-файла: {log_error}")
                
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
                logger.info(f"[{now}] Запущен концерт в чате {chat_id}")
                await msg.delete()
                
            except Exception as chat_error:
                api_monitor.record_error(chat_error, 'start_concert_job', chat_id)
                logger.error(f"[{now}] Ошибка при запуске концерта в чате {chat_id}: {chat_error}")
                await notify_admins(context, f"Ошибка при запуске концерта в чате {chat_id}:\n{str(chat_error)}")
                
    except Exception as e:
        api_monitor.record_error(e, 'start_concert_job')
        logger.error(f"[{now}] Глобальная ошибка при запуске концерта: {e}")
        await notify_admins(context, f"Глобальная ошибка при запуске концерта:\n{str(e)}")

async def stop_concert_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Остановка концерта по расписанию (23:59 МСК)"""
    now = datetime.now(moscow_tz)
    logger = logging.getLogger(__name__)
    logger.info(f"[{now}] Остановка планового концерта")
    
    try:
        context = wrap_context_bot(context)
        
        # Получаем список активных чатов
        managed_chats = await get_managed_chats(context)
        logger.info(f"[{now}] Активные чаты для остановки концерта: {managed_chats}")
        
        if not managed_chats:
            logger.warning(f"[{now}] Нет активных чатов для остановки концерта")
            return
            
        for chat_id in managed_chats:
            try:
                # Проверяем права бота перед остановкой
                bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                if not (isinstance(bot_member, ChatMemberAdministrator) and bot_member.can_restrict_members):
                    logger.error(f"[{now}] Недостаточно прав для остановки концерта в чате {chat_id}")
                    continue
                
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
                logger.info(f"[{now}] Остановлен концерт в чате {chat_id}")
                await msg.delete()
                
            except Exception as chat_error:
                api_monitor.record_error(chat_error, 'stop_concert_job', chat_id)
                logger.error(f"[{now}] Ошибка при остановке концерта в чате {chat_id}: {chat_error}")
                await notify_admins(context, f"Ошибка при остановке концерта в чате {chat_id}:\n{str(chat_error)}")
                
    except Exception as e:
        api_monitor.record_error(e, 'stop_concert_job')
        logger.error(f"[{now}] Глобальная ошибка при остановке концерта: {e}")
        await notify_admins(context, f"Глобальная ошибка при остановке концерта:\n{str(e)}")

async def get_managed_chats(context: ContextTypes.DEFAULT_TYPE) -> set:
    """Получение списка активных чатов в зависимости от режима работы"""
    context = wrap_context_bot(context)
    
    if MODE == 'secured':
        # В secured режиме работаем только с зарегистрированными чатами
        return context.bot_data.get('managed_chats', set())
    else:
        # В public режиме получаем список всех чатов, где бот является администратором
        managed_chats = set()
        if 'all_chats' in context.bot_data:
            for chat_id in context.bot_data['all_chats']:
                try:
                    bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
                    if isinstance(bot_member, ChatMemberAdministrator) and bot_member.can_restrict_members:
                        managed_chats.add(chat_id)
                except TelegramError as e:
                    api_monitor.record_error(e, 'get_chat_member', chat_id)
                    continue
        return managed_chats

async def notify_admins(context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    """Отправка уведомления администраторам"""
    context = wrap_context_bot(context)
    
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(admin_id, message)
        except Exception as e:
            api_monitor.record_error(e, 'send_message', admin_id)
            logging.error(f"Не удалось отправить сообщение администратору {admin_id}: {e}")

async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Регистрация чата для управления концертами (только в secured режиме)"""
    try:
        update = wrap_update_message(update)
        
        if MODE != 'secured':
            await update.message.reply_text("❌ Регистрация чатов доступна только в secured режиме!")
            return
            
        if update.effective_user.id not in ADMIN_CHAT_IDS:
            await update.message.reply_text("❌ Только администратор бота может регистрировать чаты!")
            return
            
        chat_id = update.effective_chat.id
        if 'managed_chats' not in context.bot_data:
            context.bot_data['managed_chats'] = set()
        
        context.bot_data['managed_chats'].add(chat_id)
        await update.message.reply_text("Чат зарегистрирован для управления концертами!")
    except Exception as e:
        api_monitor.record_error(e, 'register_chat')
        logging.error(f"Ошибка в register_chat: {e}")

async def unregister_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отмена регистрации чата (только в secured режиме)"""
    try:
        update = wrap_update_message(update)
        
        if MODE != 'secured':
            await update.message.reply_text("❌ Отмена регистрации чатов доступна только в secured режиме!")
            return
            
        if update.effective_user.id not in ADMIN_CHAT_IDS:
            await update.message.reply_text("❌ Только администратор бота может отменять регистрацию чатов!")
            return
            
        chat_id = update.effective_chat.id
        if 'managed_chats' in context.bot_data and chat_id in context.bot_data['managed_chats']:
            context.bot_data['managed_chats'].remove(chat_id)
            await update.message.reply_text("Регистрация чата отменена!")
        else:
            await update.message.reply_text("Этот чат не был зарегистрирован!")
    except Exception as e:
        api_monitor.record_error(e, 'unregister_chat')
        logging.error(f"Ошибка в unregister_chat: {e}")

async def track_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отслеживание новых чатов в public режиме"""
    try:
        if MODE != 'public':
            return
            
        chat_id = update.effective_chat.id
        if 'all_chats' not in context.bot_data:
            context.bot_data['all_chats'] = set()
        context.bot_data['all_chats'].add(chat_id)
        print(f"Бот добавлен в новый чат: {chat_id}")
    except Exception as e:
        api_monitor.record_error(e, 'track_chat')
        logging.error(f"Ошибка в track_chat: {e}")

async def get_monitoring_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для получения статистики мониторинга (только для админов)"""
    try:
        update = wrap_update_message(update)
        
        if MODE == 'secured' and update.effective_user.id not in ADMIN_CHAT_IDS:
            await update.message.reply_text("❌ Только администратор может просматривать статистику!")
            return
        
        stats = api_monitor.get_error_stats(24)  # За последние 24 часа
        health = api_monitor.get_health_status()
        
        message = f"""📊 **Статистика мониторинга за 24 часа**

🔄 **Общая статистика:**
• Всего вызовов API: {stats['total_calls']}
• Всего ошибок: {stats['total_errors']}
• Успешность: {stats['success_rate']}%
• Частота ошибок: {stats['error_rate']}%

⚠️ **Ошибки по типам:**
• 4xx ошибки: {stats['http_4xx_count']}
• 5xx ошибки: {stats['http_5xx_count']}
• Сетевые ошибки: {stats['network_errors']}
• Таймауты: {stats['timeout_errors']}
• Rate Limit: {stats['rate_limit_errors']}

🏥 **Статус системы:** {health['status']}

📈 **Мониторинг доступен по адресу:**
http://localhost:{METRICS_PORT}/dashboard
"""
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        api_monitor.record_error(e, 'get_monitoring_stats')
        logging.error(f"Ошибка в get_monitoring_stats: {e}")

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
        application.add_handler(CommandHandler("monitoring", get_monitoring_stats))
        
        # Добавляем обработчики для secured режима
        if MODE == 'secured':
            application.add_handler(CommandHandler("register_chat", register_chat))
            application.add_handler(CommandHandler("unregister_chat", unregister_chat))
        else:  # public mode
            # Отслеживаем добавление бота в новые чаты
            application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, track_chat))

        # Настройка планировщика задач с использованием cron
        job_queue = application.job_queue
        if job_queue:
            # Запуск концерта по понедельникам в 8:00 МСК
            job_queue.run_daily(
                start_concert_job,
                days=(2,),  # Понедельник
                time=time(hour=8, minute=0, tzinfo=moscow_tz)
            )
            
            # Остановка концерта каждый день в 23:59 МСК
            job_queue.run_daily(
                stop_concert_job,
                days=(2,),  # Понедельник
                time=time(hour=23, minute=59, tzinfo=moscow_tz)
            )
            
            logger.info("Планировщик задач успешно настроен")
            logger.info(f"Часовой пояс: {moscow_tz}")
            logger.info("Расписание:")
            logger.info("- Запуск концерта: каждый понедельник в 8:00 МСК")
            logger.info("- Остановка концерта: каждый день в 23:59 МСК")
        else:
            logger.error("Не удалось инициализировать планировщик задач!")
            return

        # Запуск сервера метрик в отдельной задаче
        async def start_monitoring():
            try:
                await start_metrics_server(port=METRICS_PORT)
                logger.info(f"Сервер мониторинга запущен на порту {METRICS_PORT}")
            except Exception as e:
                logger.error(f"Ошибка запуска сервера мониторинга: {e}")

        # Добавляем задачу запуска сервера мониторинга
        asyncio.create_task(start_monitoring())

        # Запуск бота с выводом информации о запуске
        logger.info("Бот запущен и готов к работе!")
        logger.info(f"Режим работы: {MODE}")
        logger.info(f"Мониторинг доступен на: http://localhost:{METRICS_PORT}")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        api_monitor.record_error(e, 'main')
        raise

if __name__ == '__main__':
    main()