#!/usr/bin/env python3
"""
Тесты для системы мониторинга Telegram API
"""

import pytest
import asyncio
import time
from monitoring import TelegramAPIMonitor, api_monitor
from telegram.error import BadRequest, NetworkError, TimedOut, Forbidden

class TestTelegramAPIMonitor:
    """Тесты для класса TelegramAPIMonitor"""
    
    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.monitor = TelegramAPIMonitor(max_history_hours=1)
    
    def test_record_successful_api_call(self):
        """Тест записи успешного API вызова"""
        self.monitor.record_api_call('send_message', True, 0.5, 123, 456)
        
        stats = self.monitor.get_error_stats(1)
        assert stats['total_calls'] == 1
        assert stats['total_errors'] == 0
        assert stats['success_rate'] == 100.0
        assert stats['error_rate'] == 0.0
    
    def test_record_failed_api_call(self):
        """Тест записи неуспешного API вызова"""
        error = BadRequest("Test error")
        error.code = 400
        
        self.monitor.record_api_call('send_message', False, 0.5, 123, 456)
        self.monitor.record_error(error, 'send_message', 123, 456)
        
        stats = self.monitor.get_error_stats(1)
        assert stats['total_calls'] == 1
        assert stats['total_errors'] == 1
        assert stats['success_rate'] == 0.0
        assert stats['error_rate'] == 100.0
        assert stats['http_4xx_count'] == 1
    
    def test_different_error_types(self):
        """Тест различных типов ошибок"""
        # 4xx ошибка
        bad_request = BadRequest("Bad request")
        bad_request.code = 400
        self.monitor.record_error(bad_request, 'send_message', 123, 456)
        
        # 5xx ошибка
        server_error = NetworkError("Server error")
        server_error.code = 500
        self.monitor.record_error(server_error, 'send_message', 123, 456)
        
        # Таймаут
        timeout = TimedOut("Timeout")
        self.monitor.record_error(timeout, 'send_message', 123, 456)
        
        # Forbidden
        forbidden = Forbidden("Forbidden")
        self.monitor.record_error(forbidden, 'send_message', 123, 456)
        
        stats = self.monitor.get_error_stats(1)
        assert stats['http_4xx_count'] == 2  # BadRequest + Forbidden
        assert stats['http_5xx_count'] == 1  # NetworkError with 5xx code
        assert stats['timeout_errors'] == 1
        assert stats['network_errors'] == 1
    
    def test_rate_limit_detection(self):
        """Тест обнаружения rate limit ошибок"""
        rate_limit_error = BadRequest("Too Many Requests: retry after 30")
        rate_limit_error.code = 429
        
        self.monitor.record_error(rate_limit_error, 'send_message', 123, 456)
        
        stats = self.monitor.get_error_stats(1)
        assert stats['rate_limit_errors'] == 1
        assert stats['http_4xx_count'] == 1
    
    def test_prometheus_metrics_format(self):
        """Тест формата метрик Prometheus"""
        self.monitor.record_api_call('send_message', True, 0.5, 123, 456)
        self.monitor.record_api_call('get_chat_member', False, 1.0, 123, 456)
        
        error = BadRequest("Test error")
        error.code = 400
        self.monitor.record_error(error, 'get_chat_member', 123, 456)
        
        metrics = self.monitor.get_prometheus_metrics()
        
        assert 'telegram_api_calls_total' in metrics
        assert 'telegram_api_errors_total' in metrics
        assert 'telegram_api_success_rate' in metrics
        assert 'telegram_api_4xx_errors_total' in metrics
        assert 'telegram_api_method_calls_total{method="send_message",status="success"}' in metrics
        assert 'telegram_api_method_calls_total{method="get_chat_member",status="error"}' in metrics
    
    def test_zabbix_metrics_format(self):
        """Тест формата метрик Zabbix"""
        self.monitor.record_api_call('send_message', True, 0.5, 123, 456)
        
        metrics = self.monitor.get_zabbix_metrics()
        
        required_keys = [
            'telegram.api.calls.total',
            'telegram.api.errors.total',
            'telegram.api.success.rate',
            'telegram.api.error.rate',
            'telegram.api.4xx.errors',
            'telegram.api.5xx.errors',
            'telegram.api.network.errors',
            'telegram.api.timeout.errors',
            'telegram.api.rate_limit.errors'
        ]
        
        for key in required_keys:
            assert key in metrics
            assert isinstance(metrics[key], (int, float))
    
    def test_health_status(self):
        """Тест определения статуса здоровья"""
        # Здоровое состояние
        for _ in range(10):
            self.monitor.record_api_call('send_message', True, 0.5, 123, 456)
        
        health = self.monitor.get_health_status()
        assert health['status'] == 'HEALTHY'
        assert health['error_rate'] == 0.0
        
        # Деградированное состояние (6% ошибок)
        self.monitor.record_api_call('send_message', False, 0.5, 123, 456)
        error = BadRequest("Test error")
        self.monitor.record_error(error, 'send_message', 123, 456)
        
        health = self.monitor.get_health_status()
        assert health['status'] == 'DEGRADED'
        
        # Критическое состояние (много ошибок)
        for _ in range(20):
            self.monitor.record_api_call('send_message', False, 0.5, 123, 456)
            self.monitor.record_error(error, 'send_message', 123, 456)
        
        health = self.monitor.get_health_status()
        assert health['status'] == 'CRITICAL'
    
    def test_metrics_cleanup(self):
        """Тест очистки старых метрик"""
        # Создаем монитор с коротким временем хранения
        short_monitor = TelegramAPIMonitor(max_history_hours=0.001)  # ~3.6 секунды
        
        # Добавляем метрику
        short_monitor.record_api_call('send_message', True, 0.5, 123, 456)
        assert len(short_monitor.api_call_metrics) == 1
        
        # Ждем и добавляем еще одну метрику (должна произойти очистка)
        time.sleep(4)
        short_monitor.record_api_call('send_message', True, 0.5, 123, 456)
        
        # Старая метрика должна быть удалена
        assert len(short_monitor.api_call_metrics) == 1
    
    def test_export_to_file(self, tmp_path):
        """Тест экспорта метрик в файл"""
        self.monitor.record_api_call('send_message', True, 0.5, 123, 456)
        
        # JSON экспорт
        json_file = tmp_path / "test_metrics.json"
        self.monitor.export_to_file(str(json_file), 'json')
        assert json_file.exists()
        
        # Prometheus экспорт
        prom_file = tmp_path / "test_metrics.prom"
        self.monitor.export_to_file(str(prom_file), 'prometheus')
        assert prom_file.exists()
        
        # Zabbix экспорт
        zabbix_file = tmp_path / "test_metrics_zabbix.json"
        self.monitor.export_to_file(str(zabbix_file), 'zabbix')
        assert zabbix_file.exists()

@pytest.mark.asyncio
async def test_monitor_async_api_call():
    """Тест асинхронного мониторинга API вызовов"""
    
    async def mock_successful_call(*args, **kwargs):
        await asyncio.sleep(0.1)
        return "success"
    
    async def mock_failing_call(*args, **kwargs):
        await asyncio.sleep(0.1)
        raise BadRequest("Test error")
    
    # Тест успешного вызова
    from monitoring import monitor_async_api_call
    result = await monitor_async_api_call(mock_successful_call, 123, user_id=456)
    assert result == "success"
    
    # Тест неуспешного вызова
    with pytest.raises(BadRequest):
        await monitor_async_api_call(mock_failing_call, 123, user_id=456)

def test_global_monitor_instance():
    """Тест глобального экземпляра монитора"""
    # Проверяем, что глобальный монитор существует
    assert api_monitor is not None
    assert isinstance(api_monitor, TelegramAPIMonitor)
    
    # Проверяем, что он работает
    api_monitor.record_api_call('test_method', True, 0.5)
    stats = api_monitor.get_error_stats(1)
    assert stats['total_calls'] >= 1

if __name__ == '__main__':
    pytest.main([__file__, '-v'])