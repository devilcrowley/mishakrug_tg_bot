import pytest
from datetime import datetime, time
import pytz
from unittest.mock import AsyncMock, MagicMock, patch
from mishakrug import start_concert_job, moscow_tz, get_managed_chats
from telegram import ChatMemberAdministrator

@pytest.mark.asyncio
async def test_start_concert_on_monday_8am():
    # Подготовка тестовых данных
    # Устанавливаем понедельник, 8:00
    test_datetime = datetime(2024, 3, 11, 8, 0, tzinfo=moscow_tz)  # 11 марта 2024 - понедельник, 8:00 МСК
    
    # Создаем мок для context.bot
    mock_bot = AsyncMock()
    mock_bot.id = 987654321  # ID бота
    mock_bot.get_chat_member = AsyncMock()
    mock_bot.set_chat_permissions = AsyncMock()
    mock_bot.send_message = AsyncMock()
    
    # Создаем мок для ChatMemberAdministrator
    mock_admin = MagicMock()
    mock_admin.can_restrict_members = True
    mock_admin.can_delete_messages = True
    mock_admin.status = 'administrator'
    mock_admin.__class__ = ChatMemberAdministrator
    
    # Настраиваем возвращаемое значение для get_chat_member
    mock_bot.get_chat_member.return_value = mock_admin
    mock_bot.get_chat_member.side_effect = None  # Убираем side_effect, чтобы всегда возвращался mock_admin
    
    # Создаем мок для context
    mock_context = MagicMock()
    mock_context.bot = mock_bot
    # В режиме public мы используем managed_chats, который формируется из all_chats после проверки прав
    mock_context.bot_data = {'managed_chats': {123456}}  # Тестовый чат ID
    
    # Создаем асинхронный мок для get_managed_chats
    async def mock_get_managed_chats(context):
        return {123456}

    # Запускаем тест с подмененными datetime.now() и get_managed_chats()
    with patch('mishakrug.datetime') as mock_datetime, \
         patch('mishakrug.get_managed_chats', side_effect=mock_get_managed_chats):
        mock_datetime.now = lambda tz=None: test_datetime  # Мокаем метод now() с поддержкой часового пояса
        
        # Вызываем тестируемую функцию
        await start_concert_job(mock_context)
        
        # Проверяем, что были вызваны нужные методы
        mock_bot.get_chat_member.assert_called_once_with(123456, mock_bot.id)
        mock_bot.set_chat_permissions.assert_called_once()
        mock_bot.send_message.assert_called_once_with(123456, "Я включаю Михаила Круга")
