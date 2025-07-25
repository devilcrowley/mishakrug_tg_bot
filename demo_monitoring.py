#!/usr/bin/env python3
"""
Демонстрационный скрипт для тестирования системы мониторинга
"""

import asyncio
import time
import random
from monitoring import api_monitor
from telegram.error import BadRequest, NetworkError, TimedOut, Forbidden

async def simulate_api_calls():
    """Симуляция различных API вызовов для демонстрации мониторинга"""
    
    print("🚀 Запуск демонстрации мониторинга Telegram API...")
    print("📊 Генерируем различные типы вызовов и ошибок...")
    
    methods = [
        'send_message',
        'get_chat_member', 
        'set_chat_permissions',
        'delete_message',
        'edit_message_text'
    ]
    
    # Симулируем 100 API вызовов
    for i in range(100):
        method = random.choice(methods)
        chat_id = random.randint(-1000000000000, -1000000000)
        user_id = random.randint(100000, 999999999)
        
        # Симулируем время ответа
        response_time = random.uniform(0.1, 2.0)
        await asyncio.sleep(0.1)  # Небольшая задержка между вызовами
        
        # 80% успешных вызовов
        if random.random() < 0.8:
            api_monitor.record_api_call(method, True, response_time, chat_id, user_id)
            if i % 10 == 0:
                print(f"✅ Успешный вызов {method} (#{i+1})")
        else:
            # Генерируем различные типы ошибок
            error_type = random.choice([
                'bad_request',
                'forbidden', 
                'network_error',
                'timeout',
                'rate_limit',
                'server_error'
            ])
            
            if error_type == 'bad_request':
                error = BadRequest("Bad Request: message not found")
                error.code = 400
            elif error_type == 'forbidden':
                error = Forbidden("Forbidden: bot was blocked by the user")
                error.code = 403
            elif error_type == 'network_error':
                error = NetworkError("Network error occurred")
                error.code = 502
            elif error_type == 'timeout':
                error = TimedOut("Timed out")
            elif error_type == 'rate_limit':
                error = BadRequest("Too Many Requests: retry after 30")
                error.code = 429
            else:  # server_error
                error = NetworkError("Internal Server Error")
                error.code = 500
            
            api_monitor.record_api_call(method, False, response_time, chat_id, user_id)
            api_monitor.record_error(error, method, chat_id, user_id)
            print(f"❌ Ошибка {error_type} в {method} (#{i+1})")
    
    print("\n📈 Демонстрация завершена! Статистика:")
    
    # Показываем статистику
    stats = api_monitor.get_error_stats(1)
    print(f"📊 Всего вызовов: {stats['total_calls']}")
    print(f"❌ Всего ошибок: {stats['total_errors']}")
    print(f"✅ Success Rate: {stats['success_rate']}%")
    print(f"📉 Error Rate: {stats['error_rate']}%")
    print(f"🔴 4xx ошибок: {stats['http_4xx_count']}")
    print(f"🔴 5xx ошибок: {stats['http_5xx_count']}")
    print(f"🌐 Сетевых ошибок: {stats['network_errors']}")
    print(f"⏰ Таймаутов: {stats['timeout_errors']}")
    print(f"🚫 Rate Limit: {stats['rate_limit_errors']}")
    
    # Показываем статус здоровья
    health = api_monitor.get_health_status()
    print(f"\n🏥 Статус системы: {health['status']}")
    
    # Экспортируем метрики
    print("\n💾 Экспорт метрик...")
    api_monitor.export_to_file('demo_metrics.json', 'json')
    api_monitor.export_to_file('demo_metrics.prom', 'prometheus')
    api_monitor.export_to_file('demo_metrics_zabbix.json', 'zabbix')
    print("✅ Метрики экспортированы в файлы:")
    print("   - demo_metrics.json (JSON)")
    print("   - demo_metrics.prom (Prometheus)")
    print("   - demo_metrics_zabbix.json (Zabbix)")
    
    print(f"\n🌐 Веб-интерфейс доступен по адресу: http://localhost:8080")
    print("📊 Эндпоинты:")
    print("   - http://localhost:8080/ (Dashboard)")
    print("   - http://localhost:8080/metrics (Prometheus)")
    print("   - http://localhost:8080/metrics/json (JSON)")
    print("   - http://localhost:8080/metrics/zabbix (Zabbix)")
    print("   - http://localhost:8080/health (Health Check)")

def print_prometheus_metrics():
    """Показать метрики в формате Prometheus"""
    print("\n📊 Метрики Prometheus:")
    print("=" * 50)
    print(api_monitor.get_prometheus_metrics())

def print_zabbix_metrics():
    """Показать метрики в формате Zabbix"""
    print("\n📊 Метрики Zabbix:")
    print("=" * 50)
    import json
    print(json.dumps(api_monitor.get_zabbix_metrics(), indent=2))

if __name__ == '__main__':
    print("🎯 Демонстрация системы мониторинга Telegram бота")
    print("=" * 60)
    
    # Запускаем симуляцию
    asyncio.run(simulate_api_calls())
    
    # Показываем метрики в разных форматах
    print_prometheus_metrics()
    print_zabbix_metrics()
    
    print("\n🎉 Демонстрация завершена!")
    print("💡 Для запуска полного мониторинга используйте:")
    print("   python mishakrug_monitored.py")