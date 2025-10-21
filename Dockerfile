FROM python:3.11-slim

# Встановлюємо змінні оточення
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Встановлюємо робочу директорію
WORKDIR /app

# Встановлюємо системні залежності
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копіюємо файл з залежностями
COPY requirements.txt .

# Встановлюємо Python залежності
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Копіюємо весь проект
COPY . .

# Відкриваємо порт для Django
EXPOSE 8000

# Команда запуску
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
