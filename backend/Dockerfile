FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VSTOCK_DB_PATH=/data/vstock.db \
    VSTOCK_AUDIO_DIR=/data/audio \
    PORT=8000 \
    QT_QPA_PLATFORM=offscreen \
    XDG_RUNTIME_DIR=/tmp/runtime-root \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        ca-certificates \
        musescore3 \
        musescore-general-soundfont \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /tmp/runtime-root /data/audio \
    && chmod 700 /tmp/runtime-root

WORKDIR /app

COPY requirements.txt .
RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY config/ config/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
