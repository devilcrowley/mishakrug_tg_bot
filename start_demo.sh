#!/bin/bash

# Скрипт для демонстрации системы мониторинга

echo "🚀 Запуск демонстрации мониторинга Telegram бота"
echo "=================================================="

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.7+"
    exit 1
fi

# Проверяем наличие pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 не найден. Установите pip"
    exit 1
fi

# Устанавливаем зависимости
echo "📦 Установка зависимостей..."
pip3 install -r requirements.txt

# Запускаем демонстрацию мониторинга
echo "🎯 Запуск демонстрации..."
python3 demo_monitoring.py

# Запускаем сервер метрик в фоне
echo "🌐 Запуск сервера метрик..."
python3 metrics_server.py &
METRICS_PID=$!

echo "✅ Сервер метрик запущен (PID: $METRICS_PID)"
echo "🌐 Веб-интерфейс: http://localhost:8080"
echo ""
echo "📊 Доступные эндпоинты:"
echo "   - http://localhost:8080/ (Dashboard)"
echo "   - http://localhost:8080/metrics (Prometheus)"
echo "   - http://localhost:8080/metrics/json (JSON)"
echo "   - http://localhost:8080/metrics/zabbix (Zabbix)"
echo "   - http://localhost:8080/health (Health Check)"
echo ""
echo "⏹️  Для остановки нажмите Ctrl+C"

# Ожидаем сигнал остановки
trap "echo '🛑 Остановка сервера...'; kill $METRICS_PID; exit 0" INT

# Ждем бесконечно
while true; do
    sleep 1
done