# Базовый образ — лёгкая версия Python (без лишнего веса, но со всем нужным для requests)
FROM python:3.11-slim

# Рабочая директория внутри контейнера
WORKDIR /app

# Сначала копируем только requirements.txt — это позволяет Docker кэшировать
# слой с установленными зависимостями и не переустанавливать их при каждой
# правке кода (пересоберётся только если сам requirements.txt изменится)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Теперь копируем остальной код проекта
COPY extractor.py validator.py report.py cli.py ./
COPY samples/ ./samples/

# Папка, куда будут складываться отчёты — можно "пробросить" наружу через volume
RUN mkdir -p /app/report_output

# По умолчанию запускаем CLI с флагом --help, чтобы контейнер без аргументов
# сразу показывал, как им пользоваться, а не падал молча
ENTRYPOINT ["python3", "cli.py"]
CMD ["--help"]
