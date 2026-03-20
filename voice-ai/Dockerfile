FROM python:3.12-slim

WORKDIR /app

# gcc is needed by lameenc (C extension) and cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent data (SQLite DB, VAPID keys, push subscriptions) goes here.
# Mount a volume at /data to survive container restarts.
ENV DATA_DIR=/data

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
