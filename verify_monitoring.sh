#!/bin/bash

# 🔍 Скрипт проверки системы мониторинга
# Проверяет все компоненты и эндпоинты

echo "🔍 Проверка системы мониторинга Telegram бота"
echo "=============================================="

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функция для проверки
check_component() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    echo -n "📋 Проверка $name... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        return 1
    fi
}

# Функция для проверки HTTP эндпоинта
check_endpoint() {
    local name="$1"
    local url="$2"
    local expected_code="$3"
    
    echo -n "🌐 Проверка $name... "
    
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    
    if [ "$response_code" = "$expected_code" ]; then
        echo -e "${GREEN}✅ OK (HTTP $response_code)${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL (HTTP $response_code, ожидался $expected_code)${NC}"
        return 1
    fi
}

# Счетчики
total_checks=0
passed_checks=0

echo ""
echo "🔧 Проверка основных компонентов:"
echo "--------------------------------"

# Проверка Python модулей
((total_checks++))
if check_component "monitoring.py" "python3 -c 'import monitoring; print(\"OK\")'" "OK"; then
    ((passed_checks++))
fi

((total_checks++))
if check_component "telegram_wrapper.py" "python3 -c 'import telegram_wrapper; print(\"OK\")'" "OK"; then
    ((passed_checks++))
fi

((total_checks++))
if check_component "simple_metrics_server.py" "python3 -c 'import simple_metrics_server; print(\"OK\")'" "OK"; then
    ((passed_checks++))
fi

echo ""
echo "📁 Проверка файлов конфигурации:"
echo "--------------------------------"

# Проверка конфигурационных файлов
config_files=(
    "monitoring_configs/prometheus/docker-compose.yml"
    "monitoring_configs/prometheus/prometheus.yml"
    "monitoring_configs/grafana/dashboard.json"
    "monitoring_configs/zabbix/telegram_bot_template.xml"
    ".env.example"
    "MONITORING_SETUP.md"
    "README_MONITORING.md"
)

for file in "${config_files[@]}"; do
    ((total_checks++))
    if check_component "$file" "test -f '$file'" ""; then
        ((passed_checks++))
    fi
done

echo ""
echo "🚀 Запуск веб-сервера метрик..."
echo "------------------------------"

# Проверяем, запущен ли уже сервер
if pgrep -f "simple_metrics_server.py" > /dev/null; then
    echo "📊 Сервер метрик уже запущен"
else
    echo "🚀 Запускаем сервер метрик..."
    python3 simple_metrics_server.py &
    SERVER_PID=$!
    sleep 3
    echo "📊 Сервер запущен (PID: $SERVER_PID)"
fi

echo ""
echo "🌐 Проверка HTTP эндпоинтов:"
echo "----------------------------"

# Проверка эндпоинтов
endpoints=(
    "Health Check|http://localhost:8080/health|200"
    "Dashboard|http://localhost:8080/|200"
    "Prometheus метрики|http://localhost:8080/metrics|200"
    "JSON метрики|http://localhost:8080/metrics/json|200"
    "Zabbix метрики|http://localhost:8080/metrics/zabbix|200"
)

for endpoint in "${endpoints[@]}"; do
    IFS='|' read -r name url code <<< "$endpoint"
    ((total_checks++))
    if check_endpoint "$name" "$url" "$code"; then
        ((passed_checks++))
    fi
done

echo ""
echo "🧪 Проверка функциональности:"
echo "-----------------------------"

# Проверка получения метрик
((total_checks++))
echo -n "📊 Получение JSON метрик... "
if json_response=$(curl -s http://localhost:8080/metrics/json 2>/dev/null) && echo "$json_response" | jq . > /dev/null 2>&1; then
    echo -e "${GREEN}✅ OK${NC}"
    ((passed_checks++))
else
    echo -e "${RED}❌ FAIL${NC}"
fi

((total_checks++))
echo -n "📈 Получение Prometheus метрик... "
if prom_response=$(curl -s http://localhost:8080/metrics 2>/dev/null) && echo "$prom_response" | grep -q "telegram_api"; then
    echo -e "${GREEN}✅ OK${NC}"
    ((passed_checks++))
else
    echo -e "${RED}❌ FAIL${NC}"
fi

echo ""
echo "🧪 Запуск демонстрации:"
echo "----------------------"

((total_checks++))
echo -n "🎯 Демо мониторинга... "
if python3 demo_monitoring.py > /dev/null 2>&1; then
    echo -e "${GREEN}✅ OK${NC}"
    ((passed_checks++))
else
    echo -e "${RED}❌ FAIL${NC}"
fi

echo ""
echo "📊 Результаты проверки:"
echo "======================"

success_rate=$((passed_checks * 100 / total_checks))

echo "📋 Всего проверок: $total_checks"
echo "✅ Успешных: $passed_checks"
echo "❌ Неудачных: $((total_checks - passed_checks))"
echo "📈 Успешность: $success_rate%"

if [ $success_rate -ge 90 ]; then
    echo -e "${GREEN}🎉 Система мониторинга работает отлично!${NC}"
    exit_code=0
elif [ $success_rate -ge 70 ]; then
    echo -e "${YELLOW}⚠️  Система мониторинга работает с предупреждениями${NC}"
    exit_code=1
else
    echo -e "${RED}🚨 Система мониторинга имеет критические проблемы${NC}"
    exit_code=2
fi

echo ""
echo "🔗 Полезные ссылки:"
echo "==================="
echo "📊 Dashboard: http://localhost:8080/"
echo "🏥 Health Check: http://localhost:8080/health"
echo "📈 Prometheus: http://localhost:8080/metrics"
echo "📋 JSON метрики: http://localhost:8080/metrics/json"
echo "🔧 Zabbix метрики: http://localhost:8080/metrics/zabbix"

echo ""
echo "📚 Документация:"
echo "================"
echo "📖 Быстрый старт: README_MONITORING.md"
echo "🔧 Настройка: MONITORING_SETUP.md"
echo "📊 Отчет: IMPLEMENTATION_REPORT.md"

echo ""
echo "🚀 Команды для запуска:"
echo "======================"
echo "🎯 Демо: ./start_demo.sh"
echo "🤖 Бот с мониторингом: python3 mishakrug_monitored.py"
echo "🧪 Тесты: python3 test_monitoring.py"

exit $exit_code