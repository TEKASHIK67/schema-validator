# Используем официальный образ Microsoft Playwright для Python v1.61.0
FROM mcr.microsoft.com/playwright/python:v1.61.0-jammy

# Установка рабочей директории в контейнере
WORKDIR /app

# Установка необходимых дополнительных библиотек
RUN pip install --no-cache-dir playwright-stealth extruct

# Копирование исходных файлов проекта в контейнер
COPY cli.py extractor.py validator.py report.py ./

# Копируем папку samples (вместе с файлом urls_hotels.txt)
COPY samples/ ./samples/

# Делаем CLI-файл исполняемым
RUN chmod +x cli.py

# Задаем точку входа по умолчанию
ENTRYPOINT ["python", "cli.py"]