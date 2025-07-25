#!/usr/bin/env python3
"""
Простой HTTP сервер для экспорта метрик мониторинга
"""

import json
import asyncio
from datetime import datetime
from aiohttp import web
from monitoring import api_monitor
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('simple_metrics_server')


async def health_check(request):
    """Эндпоинт для проверки здоровья"""
    try:
        health = api_monitor.get_health_status()
        status_code = 200 if health['status'] == 'HEALTHY' else 503
        return web.json_response(health, status=status_code)
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def prometheus_metrics(request):
    """Эндпоинт для метрик Prometheus"""
    try:
        metrics = api_monitor.get_prometheus_metrics()
        return web.Response(
            text=metrics,
            content_type='text/plain; version=0.0.4',
            charset='utf-8'
        )
    except Exception as e:
        logger.error(f"Ошибка при генерации метрик Prometheus: {e}")
        return web.Response(text=f"Error: {str(e)}", status=500)


async def json_metrics(request):
    """Эндпоинт для метрик в формате JSON"""
    try:
        hours = int(request.query.get('hours', 1))
        stats = api_monitor.get_error_stats(hours)
        return web.json_response(stats)
    except Exception as e:
        logger.error(f"Ошибка при генерации JSON метрик: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def zabbix_metrics(request):
    """Эндпоинт для метрик Zabbix"""
    try:
        metrics = api_monitor.get_zabbix_metrics()
        return web.json_response(metrics)
    except Exception as e:
        logger.error(f"Ошибка при генерации Zabbix метрик: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def metrics_dashboard(request):
    """Простая HTML панель с метриками"""
    try:
        stats = api_monitor.get_error_stats(24)
        health = api_monitor.get_health_status()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Telegram Bot Monitoring</title>
            <meta charset="utf-8">
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .status-healthy {{ color: green; font-weight: bold; }}
                .status-degraded {{ color: blue; font-weight: bold; }}
                .status-warning {{ color: orange; font-weight: bold; }}
                .status-critical {{ color: red; font-weight: bold; }}
                .metric {{ margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
                .error {{ background-color: #ffe6e6; }}
                .success {{ background-color: #e6ffe6; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Telegram Bot Monitoring Dashboard</h1>
            <p>Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="metric">
                <h2>Статус системы: <span class="status-{health['status'].lower()}">{health['status']}</span></h2>
                <p>Успешность: {health['success_rate']}%</p>
                <p>Частота ошибок: {health['error_rate']}%</p>
            </div>
            
            <div class="metric {'success' if stats['error_rate'] < 5 else 'error'}">
                <h3>Статистика за 24 часа</h3>
                <p>Всего вызовов API: {stats['total_calls']}</p>
                <p>Всего ошибок: {stats['total_errors']}</p>
                <p>Успешность: {stats['success_rate']}%</p>
                <p>Частота ошибок: {stats['error_rate']}%</p>
            </div>
            
            <div class="metric">
                <h3>Ошибки по типам</h3>
                <table>
                    <tr><th>Тип ошибки</th><th>Количество</th></tr>
                    <tr><td>4xx ошибки</td><td>{stats['http_4xx_count']}</td></tr>
                    <tr><td>5xx ошибки</td><td>{stats['http_5xx_count']}</td></tr>
                    <tr><td>Сетевые ошибки</td><td>{stats['network_errors']}</td></tr>
                    <tr><td>Таймауты</td><td>{stats['timeout_errors']}</td></tr>
                    <tr><td>Rate Limit</td><td>{stats['rate_limit_errors']}</td></tr>
                </table>
            </div>
            
            <div class="metric">
                <h3>Последние ошибки</h3>
                <table>
                    <tr><th>Время</th><th>Тип</th><th>Метод</th><th>Сообщение</th></tr>
        """
        
        for error in health['recent_errors']:
            error_time = datetime.fromtimestamp(error['timestamp']).strftime('%H:%M:%S')
            html += f"""
                <tr>
                    <td>{error_time}</td>
                    <td>{error['error_type']}</td>
                    <td>{error['method_name']}</td>
                    <td>{error['error_message'][:100]}...</td>
                </tr>
            """
        
        html += """
                </table>
            </div>
            
            <div class="metric">
                <h3>Эндпоинты мониторинга</h3>
                <ul>
                    <li><a href="/metrics">Prometheus метрики</a></li>
                    <li><a href="/metrics/json">JSON метрики</a></li>
                    <li><a href="/metrics/zabbix">Zabbix метрики</a></li>
                    <li><a href="/health">Health Check</a></li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        return web.Response(text=html, content_type='text/html')
    except Exception as e:
        logger.error(f"Ошибка при генерации дашборда: {e}")
        return web.Response(text=f"Error: {str(e)}", status=500)


async def create_app():
    """Создание приложения"""
    app = web.Application()
    
    # Добавляем маршруты
    app.router.add_get('/health', health_check)
    app.router.add_get('/metrics', prometheus_metrics)
    app.router.add_get('/metrics/json', json_metrics)
    app.router.add_get('/metrics/zabbix', zabbix_metrics)
    app.router.add_get('/', metrics_dashboard)
    app.router.add_get('/dashboard', metrics_dashboard)
    
    return app


async def main():
    """Главная функция"""
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    
    logger.info("Сервер метрик запущен на http://0.0.0.0:8080")
    logger.info("Доступные эндпоинты:")
    logger.info("  - Dashboard: http://0.0.0.0:8080/")
    logger.info("  - Prometheus: http://0.0.0.0:8080/metrics")
    logger.info("  - JSON: http://0.0.0.0:8080/metrics/json")
    logger.info("  - Zabbix: http://0.0.0.0:8080/metrics/zabbix")
    logger.info("  - Health: http://0.0.0.0:8080/health")
    
    # Ждем бесконечно
    try:
        await asyncio.Future()  # run forever
    except KeyboardInterrupt:
        logger.info("Остановка сервера...")
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(main())