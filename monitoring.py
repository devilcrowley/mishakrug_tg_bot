"""
Модуль мониторинга для отслеживания ошибок Telegram API
Поддерживает экспорт метрик для Prometheus, Grafana и Zabbix
"""

import time
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from telegram.error import TelegramError, BadRequest, Forbidden, NetworkError, TimedOut

# Настройка логгера для мониторинга
monitoring_logger = logging.getLogger('telegram_monitoring')
monitoring_logger.setLevel(logging.INFO)

# Создаем отдельный файл для логов мониторинга
monitoring_handler = logging.FileHandler('telegram_monitoring.log')
monitoring_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
monitoring_handler.setFormatter(monitoring_formatter)
monitoring_logger.addHandler(monitoring_handler)


@dataclass
class ErrorMetric:
    """Метрика ошибки API"""
    timestamp: float
    error_type: str
    error_code: Optional[int]
    error_message: str
    method_name: str
    chat_id: Optional[int]
    user_id: Optional[int]
    retry_count: int = 0


@dataclass
class APICallMetric:
    """Метрика вызова API"""
    timestamp: float
    method_name: str
    success: bool
    response_time: float
    chat_id: Optional[int] = None
    user_id: Optional[int] = None


class TelegramAPIMonitor:
    """Класс для мониторинга Telegram API"""
    
    def __init__(self, max_history_hours: int = 24):
        self.max_history_hours = max_history_hours
        self.error_metrics: deque = deque()
        self.api_call_metrics: deque = deque()
        self.error_counters: Dict[str, int] = defaultdict(int)
        self.method_counters: Dict[str, Dict[str, int]] = defaultdict(lambda: {'success': 0, 'error': 0})
        self.lock = threading.Lock()
        
        # Счетчики для различных типов ошибок
        self.http_4xx_count = 0
        self.http_5xx_count = 0
        self.network_error_count = 0
        self.timeout_error_count = 0
        self.rate_limit_count = 0
        
        # Последние ошибки для быстрого доступа
        self.recent_errors: deque = deque(maxlen=100)
        
        monitoring_logger.info("Telegram API Monitor инициализирован")
    
    def record_api_call(self, method_name: str, success: bool, response_time: float, 
                       chat_id: Optional[int] = None, user_id: Optional[int] = None):
        """Записать метрику вызова API"""
        with self.lock:
            metric = APICallMetric(
                timestamp=time.time(),
                method_name=method_name,
                success=success,
                response_time=response_time,
                chat_id=chat_id,
                user_id=user_id
            )
            
            self.api_call_metrics.append(metric)
            
            # Обновляем счетчики
            if success:
                self.method_counters[method_name]['success'] += 1
            else:
                self.method_counters[method_name]['error'] += 1
            
            self._cleanup_old_metrics()
    
    def record_error(self, error: Exception, method_name: str, 
                    chat_id: Optional[int] = None, user_id: Optional[int] = None, 
                    retry_count: int = 0):
        """Записать ошибку API"""
        with self.lock:
            error_type = type(error).__name__
            error_code = getattr(error, 'code', None) if hasattr(error, 'code') else None
            error_message = str(error)
            
            # Определяем тип ошибки для счетчиков
            if isinstance(error, BadRequest):
                if error_code and 400 <= error_code < 500:
                    self.http_4xx_count += 1
            elif isinstance(error, Forbidden):
                self.http_4xx_count += 1
            elif isinstance(error, NetworkError):
                self.network_error_count += 1
                if error_code and 500 <= error_code < 600:
                    self.http_5xx_count += 1
            elif isinstance(error, TimedOut):
                self.timeout_error_count += 1
            elif "rate limit" in error_message.lower() or "too many requests" in error_message.lower():
                self.rate_limit_count += 1
                self.http_4xx_count += 1
            
            metric = ErrorMetric(
                timestamp=time.time(),
                error_type=error_type,
                error_code=error_code,
                error_message=error_message,
                method_name=method_name,
                chat_id=chat_id,
                user_id=user_id,
                retry_count=retry_count
            )
            
            self.error_metrics.append(metric)
            self.error_counters[error_type] += 1
            self.recent_errors.append(metric)
            
            # Логируем ошибку
            monitoring_logger.error(
                f"Telegram API Error: {error_type} in {method_name} - "
                f"Code: {error_code}, Message: {error_message}, "
                f"Chat: {chat_id}, User: {user_id}, Retry: {retry_count}"
            )
            
            self._cleanup_old_metrics()
    
    def _cleanup_old_metrics(self):
        """Очистка старых метрик"""
        cutoff_time = time.time() - (self.max_history_hours * 3600)
        
        # Очищаем старые метрики ошибок
        while self.error_metrics and self.error_metrics[0].timestamp < cutoff_time:
            self.error_metrics.popleft()
        
        # Очищаем старые метрики вызовов API
        while self.api_call_metrics and self.api_call_metrics[0].timestamp < cutoff_time:
            self.api_call_metrics.popleft()
    
    def get_error_stats(self, hours: int = 1) -> Dict[str, Any]:
        """Получить статистику ошибок за указанный период"""
        try:
            # Используем timeout для блокировки
            if self.lock.acquire(timeout=1.0):
                try:
                    cutoff_time = time.time() - (hours * 3600)
                    
                    recent_errors = [m for m in self.error_metrics if m.timestamp >= cutoff_time]
                    recent_calls = [m for m in self.api_call_metrics if m.timestamp >= cutoff_time]
                finally:
                    self.lock.release()
            else:
                # Если не удалось получить блокировку, возвращаем пустую статистику
                recent_errors = []
                recent_calls = []
            
            error_by_type = defaultdict(int)
            error_by_method = defaultdict(int)
            error_by_code = defaultdict(int)
            
            for error in recent_errors:
                error_by_type[error.error_type] += 1
                error_by_method[error.method_name] += 1
                if error.error_code:
                    error_by_code[error.error_code] += 1
            
            total_calls = len(recent_calls)
            total_errors = len(recent_errors)
            success_rate = ((total_calls - total_errors) / total_calls * 100) if total_calls > 0 else 100
            
            return {
                'period_hours': hours,
                'total_calls': total_calls,
                'total_errors': total_errors,
                'success_rate': round(success_rate, 2),
                'error_rate': round((total_errors / total_calls * 100) if total_calls > 0 else 0, 2),
                'errors_by_type': dict(error_by_type),
                'errors_by_method': dict(error_by_method),
                'errors_by_code': dict(error_by_code),
                'http_4xx_count': sum(1 for e in recent_errors if e.error_code and 400 <= e.error_code < 500),
                'http_5xx_count': sum(1 for e in recent_errors if e.error_code and 500 <= e.error_code < 600),
                'network_errors': sum(1 for e in recent_errors if e.error_type == 'NetworkError'),
                'timeout_errors': sum(1 for e in recent_errors if e.error_type == 'TimedOut'),
                'rate_limit_errors': sum(1 for e in recent_errors if 'rate limit' in e.error_message.lower())
            }
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return {
                'period_hours': hours,
                'total_calls': 0,
                'total_errors': 0,
                'success_rate': 100,
                'error_rate': 0,
                'errors_by_type': {},
                'errors_by_method': {},
                'errors_by_code': {},
                'http_4xx_count': 0,
                'http_5xx_count': 0,
                'network_errors': 0,
                'timeout_errors': 0,
                'rate_limit_errors': 0
            }
    
    def get_prometheus_metrics(self) -> str:
        """Экспорт метрик в формате Prometheus"""
        try:
            # Получаем статистику без блокировки, чтобы избежать рекурсии
            cutoff_time = time.time() - 3600  # За последний час
            
            # Копируем данные без блокировки
            recent_errors = [m for m in self.error_metrics if m.timestamp >= cutoff_time]
            recent_calls = [m for m in self.api_call_metrics if m.timestamp >= cutoff_time]
            
            total_calls = len(recent_calls)
            total_errors = len(recent_errors)
            success_rate = ((total_calls - total_errors) / total_calls * 100) if total_calls > 0 else 100
            error_rate = (total_errors / total_calls * 100) if total_calls > 0 else 0
            
            http_4xx_count = sum(1 for e in recent_errors if e.error_code and 400 <= e.error_code < 500)
            http_5xx_count = sum(1 for e in recent_errors if e.error_code and 500 <= e.error_code < 600)
            network_errors = sum(1 for e in recent_errors if e.error_type == 'NetworkError')
            timeout_errors = sum(1 for e in recent_errors if e.error_type == 'TimedOut')
            rate_limit_errors = sum(1 for e in recent_errors if 'rate limit' in e.error_message.lower())
            
            metrics = []
            
            # Общие метрики
            metrics.append(f"telegram_api_calls_total {total_calls}")
            metrics.append(f"telegram_api_errors_total {total_errors}")
            metrics.append(f"telegram_api_success_rate {success_rate:.2f}")
            metrics.append(f"telegram_api_error_rate {error_rate:.2f}")
            
            # Метрики по типам ошибок
            metrics.append(f"telegram_api_4xx_errors_total {http_4xx_count}")
            metrics.append(f"telegram_api_5xx_errors_total {http_5xx_count}")
            metrics.append(f"telegram_api_network_errors_total {network_errors}")
            metrics.append(f"telegram_api_timeout_errors_total {timeout_errors}")
            metrics.append(f"telegram_api_rate_limit_errors_total {rate_limit_errors}")
            
            # Метрики по методам
            for method, counts in self.method_counters.items():
                metrics.append(f'telegram_api_method_calls_total{{method="{method}",status="success"}} {counts["success"]}')
                metrics.append(f'telegram_api_method_calls_total{{method="{method}",status="error"}} {counts["error"]}')
            
            # Метрики по кодам ошибок
            error_by_code = defaultdict(int)
            for error in recent_errors:
                if error.error_code:
                    error_by_code[error.error_code] += 1
            
            for code, count in error_by_code.items():
                metrics.append(f'telegram_api_error_code_total{{code="{code}"}} {count}')
            
            return '\n'.join(metrics)
        except Exception as e:
            logger.error(f"Ошибка при генерации Prometheus метрик: {e}")
            return "# Error generating metrics"
    
    def get_zabbix_metrics(self) -> Dict[str, Any]:
        """Экспорт метрик для Zabbix"""
        stats = self.get_error_stats(1)
        
        return {
            'telegram.api.calls.total': stats['total_calls'],
            'telegram.api.errors.total': stats['total_errors'],
            'telegram.api.success.rate': stats['success_rate'],
            'telegram.api.error.rate': stats['error_rate'],
            'telegram.api.4xx.errors': stats['http_4xx_count'],
            'telegram.api.5xx.errors': stats['http_5xx_count'],
            'telegram.api.network.errors': stats['network_errors'],
            'telegram.api.timeout.errors': stats['timeout_errors'],
            'telegram.api.rate_limit.errors': stats['rate_limit_errors']
        }
    
    def export_to_file(self, filepath: str, format_type: str = 'json'):
        """Экспорт метрик в файл"""
        stats = self.get_error_stats(24)  # За последние 24 часа
        
        if format_type == 'json':
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        elif format_type == 'prometheus':
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(self.get_prometheus_metrics())
        elif format_type == 'zabbix':
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.get_zabbix_metrics(), f, indent=2)
        
        monitoring_logger.info(f"Метрики экспортированы в {filepath} (формат: {format_type})")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получить статус здоровья API"""
        stats = self.get_error_stats(1)
        
        # Определяем статус на основе метрик
        if stats['error_rate'] > 50:
            status = 'CRITICAL'
        elif stats['error_rate'] > 20:
            status = 'WARNING'
        elif stats['error_rate'] > 5:
            status = 'DEGRADED'
        else:
            status = 'HEALTHY'
        
        return {
            'status': status,
            'error_rate': stats['error_rate'],
            'success_rate': stats['success_rate'],
            'total_calls': stats['total_calls'],
            'total_errors': stats['total_errors'],
            'last_check': datetime.now().isoformat(),
            'recent_errors': [asdict(error) for error in list(self.recent_errors)[-5:]]
        }


# Глобальный экземпляр монитора
api_monitor = TelegramAPIMonitor()


def monitor_api_call(func):
    """Декоратор для мониторинга вызовов API"""
    def wrapper(*args, **kwargs):
        method_name = func.__name__
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            response_time = time.time() - start_time
            api_monitor.record_api_call(method_name, True, response_time)
            return result
        except TelegramError as e:
            response_time = time.time() - start_time
            api_monitor.record_api_call(method_name, False, response_time)
            api_monitor.record_error(e, method_name)
            raise
        except Exception as e:
            response_time = time.time() - start_time
            api_monitor.record_api_call(method_name, False, response_time)
            api_monitor.record_error(e, method_name)
            raise
    
    return wrapper


async def monitor_async_api_call(func, *args, **kwargs):
    """Асинхронный мониторинг вызовов API"""
    method_name = func.__name__ if hasattr(func, '__name__') else str(func)
    start_time = time.time()
    
    # Извлекаем chat_id и user_id из аргументов если возможно
    chat_id = None
    user_id = None
    
    if args:
        # Пытаемся найти chat_id в аргументах
        for arg in args:
            if isinstance(arg, int) and abs(arg) > 1000:  # Предполагаем что это chat_id
                chat_id = arg
                break
    
    if 'chat_id' in kwargs:
        chat_id = kwargs['chat_id']
    if 'user_id' in kwargs:
        user_id = kwargs['user_id']
    
    try:
        result = await func(*args, **kwargs)
        response_time = time.time() - start_time
        api_monitor.record_api_call(method_name, True, response_time, chat_id, user_id)
        return result
    except TelegramError as e:
        response_time = time.time() - start_time
        api_monitor.record_api_call(method_name, False, response_time, chat_id, user_id)
        api_monitor.record_error(e, method_name, chat_id, user_id)
        raise
    except Exception as e:
        response_time = time.time() - start_time
        api_monitor.record_api_call(method_name, False, response_time, chat_id, user_id)
        api_monitor.record_error(e, method_name, chat_id, user_id)
        raise