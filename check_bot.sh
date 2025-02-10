#!/bin/bash

# Проверяем, запущен ли бот
if ! pgrep -f "python3 mishakrug.py"; then
    # Если бот не запущен, запускаем его
    python3 /path/to/your/mishakrug.py &
    echo "Бот запущен."
else
    echo "Бот уже работает."
fi
