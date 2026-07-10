# Базовый образ — лёгкая версия Python
FROM python:3.11-slim

WORKDIR /app

# Сначала копируем requirements.txt отдельно — так Docker кэширует этот слой
# и не переустанавливает всё заново при каждой правке кода
COPY requirements.txt .

# Устанавливаем Python-зависимости, а затем сам браузер Chromium вместе со
# всеми системными библиотеками, которые ему нужны (--with-deps сам
# определяет и ставит через apt всё необходимое — шрифты, кодеки и т.д.).
# Это самый тяжёлый и долгий шаг сборки образа (может занять несколько минут
# и добавить прилично веса), но без него Playwright не сможет запустить
# headless-браузер внутри контейнера.
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

# Копируем код проекта
COPY extractor.py validator.py report.py cli.py ./
COPY samples/ ./samples/

# Папка для отчётов (в т.ч. порционных result/*)
RUN mkdir -p /app/report_output

ENTRYPOINT ["python3", "cli.py"]
CMD ["--help"]
