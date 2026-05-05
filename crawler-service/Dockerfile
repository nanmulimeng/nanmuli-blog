# Web Collector - Crawler Service Dockerfile
# 基于微软 Playwright 官方镜像，已预装 Chromium
# 支持双模式部署：纯 API 模式 / 独立模式

FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY main.py .
COPY config.py .
COPY api/ ./api/
COPY crawler/ ./crawler/
COPY standalone/ ./standalone/

# 创建数据目录和非 root 用户
RUN mkdir -p /app/data /app/exports && \
    useradd -m crawler && chown -R crawler:crawler /app
USER crawler

EXPOSE 8500

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8500/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8500", "--workers", "1"]
