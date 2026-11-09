# Imagen del bot E2-A (Binance DEMO). Construcción reproducible (RNF-02).
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    BOT_CONFIG=/bot/config/bot.yaml

WORKDIR /bot

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config
COPY .env ./.env

RUN useradd --create-home --uid 1000 bot \
    && mkdir -p /bot/runs \
    && chown -R bot:bot /bot
USER bot

HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import os,sys; p=os.path.join('runs', os.environ.get('BOT_RUN_ID','e2a-demo-001')); sys.exit(0 if os.path.exists(os.path.join(p,'state.json')) else 1)"

ENTRYPOINT ["python", "-m", "app.main"]
CMD ["--config", "/bot/config/bot.yaml"]
