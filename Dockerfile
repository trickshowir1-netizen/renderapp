FROM python:3.11-slim

# نصب پیش‌نیازهای سیستمی برای Pillow
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
