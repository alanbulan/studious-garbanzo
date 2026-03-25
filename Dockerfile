FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=20080 \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=8 \
    GUNICORN_TIMEOUT=120

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 20080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:20080/ >/dev/null || exit 1

CMD ["sh", "-c", "exec gunicorn --worker-class gthread --workers ${GUNICORN_WORKERS:-1} --threads ${GUNICORN_THREADS:-8} --bind 0.0.0.0:${PORT:-20080} --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile - --error-logfile - webui:app"]
