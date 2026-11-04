FROM node:22-slim AS interface
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NEXO_HOST=0.0.0.0 \
    NEXO_PORT=8000 \
    NEXO_DATA_DIR=/dados \
    HF_HOME=/dados/modelos
WORKDIR /app
COPY requirements.txt ./
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install -r requirements.txt
COPY nexo ./nexo
COPY scripts ./scripts
COPY exemplos ./exemplos
COPY VERSION pyproject.toml .env.example ./
COPY --from=interface /app/frontend/dist ./frontend/dist
RUN useradd --create-home --uid 10001 nexo && mkdir -p /dados && chown -R nexo:nexo /dados
USER nexo
VOLUME ["/dados"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=4).status == 200 else 1)"
CMD ["python", "-m", "nexo"]
