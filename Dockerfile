FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Build tools and the JSON header required by the C++ JSONL executable.
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY backend/ ./backend/
COPY cpp/ ./cpp/
COPY frontend/ ./frontend/

# Always compile for the deployment platform. Do not ship the local Mac binary.
RUN mkdir -p build \
    && g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic \
       -Icpp/include \
       cpp/src/exchange.cpp cpp/src/main.cpp \
       -o build/aegis_engine

EXPOSE 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
