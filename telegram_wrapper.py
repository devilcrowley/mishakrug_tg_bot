"""
Обертка для Telegram API с мониторингом
"""

from typing import Any, Optional
from telegram import Bot, Update, Message
from telegram.ext import ContextTypes
from monitoring import monitor_async_api_call, api_monitor


class MonitoredBot:
    """Обертка для Bot с мониторингом всех API вызовов"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def get_chat_member(self, chat_id: int, user_id: int, **kwargs):
        """Получить информацию о участнике чата"""
        return await monitor_async_api_call(
            self.bot.get_chat_member, chat_id, user_id, **kwargs
        )
    
    async def set_chat_permissions(self, chat_id: int, permissions, **kwargs):
        """Установить права чата"""
        return await monitor_async_api_call(
            self.bot.set_chat_permissions, chat_id, permissions, **kwargs
        )
    
    async def send_message(self, chat_id: int, text: str, **kwargs):
        """Отправить сообщение"""
        return await monitor_async_api_call(
            self.bot.send_message, chat_id, text, **kwargs
        )
    
    async def delete_message(self, chat_id: int, message_id: int, **kwargs):
        """Удалить сообщение"""
        return await monitor_async_api_call(
            self.bot.delete_message, chat_id, message_id, **kwargs
        )
    
    def __getattr__(self, name):
        """Проксирование всех остальных атрибутов к оригинальному боту"""
        return getattr(self.bot, name)


class MonitoredMessage:
    """Обертка для Message с мониторингом"""
    
    def __init__(self, message: Message):
        self.message = message
    
    async def reply_text(self, text: str, **kwargs):
        """Ответить на сообщение"""
        return await monitor_async_api_call(
            self.message.reply_text, text, **kwargs
        )
    
    async def delete(self, **kwargs):
        """Удалить сообщение"""
        return await monitor_async_api_call(
            self.message.delete, **kwargs
        )
    
    async def edit_text(self, text: str, **kwargs):
        """Редактировать текст сообщения"""
        return await monitor_async_api_call(
            self.message.edit_text, text, **kwargs
        )
    
    def __getattr__(self, name):
        """Проксирование всех остальных атрибутов к оригинальному сообщению"""
        return getattr(self.message, name)


def wrap_context_bot(context: ContextTypes.DEFAULT_TYPE) -> ContextTypes.DEFAULT_TYPE:
    """Обернуть бота в контексте для мониторинга"""
    if not hasattr(context, '_monitored_bot'):
        context._monitored_bot = MonitoredBot(context.bot)
        context.bot = context._monitored_bot
    return context


def wrap_update_message(update: Update) -> Update:
    """Обернуть сообщение в update для мониторинга"""
    if update.message and not hasattr(update.message, '_monitored'):
        update.message = MonitoredMessage(update.message)
        update.message._monitored = True
    return update