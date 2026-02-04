FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Sistem bağımlılıkları (watchdog için çoğu zaman gerekmez ama güvenli)
RUN pip install --no-cache-dir --upgrade pip

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App
# App
COPY . .

# Default: çalıştır
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]


