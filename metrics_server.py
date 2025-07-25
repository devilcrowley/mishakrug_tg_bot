"""
HTTP сервер для экспорта метрик мониторинга
Поддерживает форматы: Prometheus, JSON, Zabbix
"""

import json
import asyncio
from datetime import datetime
from aiohttp import web
from aiohttp.web_response import Response
from monitoring import api_monitor
import logging

# Настройка логгера
logger = logging.getLogger('metrics_server')


async def prometheus_metrics(request: web.Request) -> Response:
    """Эндпоинт для метрик Prometheus"""
    try:
        metrics = api_monitor.get_prometheus_metrics()
        return Response(
            text=metrics,
            content_type='text/plain; version=0.0.4; charset=utf-8'
        )
    except Exception as e:
        logger.error(f"Ошибка при генерации метрик Prometheus: {e}")
        return Response(text=f"Error: {str(e)}", status=500)


async def json_metrics(request: web.Request) -> Response:
    """Эндпоинт для метрик в формате JSON"""
    try:
        hours = int(request.query.get('hours', 1))
        stats = api_monitor.get_error_stats(hours)
        return web.json_response(stats)
    except Exception as e:
        logger.error(f"Ошибка при генерации JSON метрик: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def zabbix_metrics(request: web.Request) -> Response:
    """Эндпоинт для метрик Zabbix"""
    try:
        metrics = api_monitor.get_zabbix_metrics()
        return web.json_response(metrics)
    except Exception as e:
        logger.error(f"Ошибка при генерации метрик Zabbix: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def health_check(request: web.Request) -> Response:
    """Эндпоинт для проверки здоровья"""
    try:
        health = api_monitor.get_health_status()
        status_code = 200
        
        if health['status'] in ['CRITICAL', 'WARNING']:
            status_code = 503
        elif health['status'] == 'DEGRADED':
            status_code = 200
            
        return web.json_response(health, status=status_code)
    except Exception as e:
        logger.error(f"Ошибка при проверке здоровья: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def metrics_dashboard(request: web.Request) -> Response:
    """Простая HTML панель с метриками"""
    try:
        stats = api_monitor.get_error_stats(24)
        health = api_monitor.get_health_status()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Telegram Bot Monitoring Dashboard</title>
            <meta charset="utf-8">
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .status-{health['status'].lower()} {{ 
                    color: {'red' if health['status'] == 'CRITICAL' else 'orange' if health['status'] == 'WARNING' else 'blue' if health['status'] == 'DEGRADED' else 'green'};
                    font-weight: bold;
                }}
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
                <h3>Ошибки по методам API</h3>
                <table>
                    <tr><th>Метод</th><th>Количество ошибок</th></tr>
        """
        
        for method, count in stats['errors_by_method'].items():
            html += f"<tr><td>{method}</td><td>{count}</td></tr>"
        
        html += """
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
        
        return Response(text=html, content_type='text/html')
    except Exception as e:
        logger.error(f"Ошибка при генерации дашборда: {e}")
        return Response(text=f"Error: {str(e)}", status=500)


async def create_metrics_server(host: str = '0.0.0.0', port: int = 8080) -> web.Application:
    """Создание и настройка веб-сервера метрик"""
    app = web.Application()
    
    # Добавляем маршруты
    app.router.add_get('/metrics', prometheus_metrics)
    app.router.add_get('/metrics/json', json_metrics)
    app.router.add_get('/metrics/zabbix', zabbix_metrics)
    app.router.add_get('/health', health_check)
    app.router.add_get('/', metrics_dashboard)
    app.router.add_get('/dashboard', metrics_dashboard)
    
    # CORS headers для всех ответов
    async def add_cors_headers(request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    app.middlewares.append(add_cors_headers)
    
    logger.info(f"Сервер метрик настроен на {host}:{port}")
    return app


async def start_metrics_server(host: str = '0.0.0.0', port: int = 8080):
    """Запуск сервера метрик"""
    app = await create_metrics_server(host, port)
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info(f"Сервер метрик запущен на http://{host}:{port}")
    logger.info("Доступные эндпоинты:")
    logger.info(f"  - Dashboard: http://{host}:{port}/")
    logger.info(f"  - Prometheus: http://{host}:{port}/metrics")
    logger.info(f"  - JSON: http://{host}:{port}/metrics/json")
    logger.info(f"  - Zabbix: http://{host}:{port}/metrics/zabbix")
    logger.info(f"  - Health: http://{host}:{port}/health")
    
    return runner


if __name__ == '__main__':
    # Запуск сервера метрик как отдельного приложения
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        runner = await start_metrics_server()
        try:
            while True:
                await asyncio.sleep(3600)  # Работаем бесконечно
        except KeyboardInterrupt:
            logger.info("Остановка сервера метрик...")
        finally:
            await runner.cleanup()
    
    asyncio.run(main())