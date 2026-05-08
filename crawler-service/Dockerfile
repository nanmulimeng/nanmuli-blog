# Web Collector - Crawler Service Dockerfile
# 基于微软 Playwright 官方镜像，已预装 Chromium
# 支持双模式部署：纯 API 模式 / 独立模式

# Builder: install Python dependencies
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime: minimal layer
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy application code
COPY main.py config.py ./
COPY api/ ./api/
COPY ai/ ./ai/
COPY crawler/ ./crawler/
COPY standalone/ ./standalone/

# Create data directory and non-root user
RUN mkdir -p /app/data /app/exports && \
    useradd -m crawler && chown -R crawler:crawler /app
USER crawler

EXPOSE 8500

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8500/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8500", "--workers", "1"]
