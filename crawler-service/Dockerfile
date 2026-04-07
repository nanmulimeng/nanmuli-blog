# Web Collector - Crawler Service Dockerfile
# 基于微软 Playwright 官方镜像，已预装 Chromium

FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY main.py .
COPY crawler/ ./crawler/

# 创建非 root 用户运行应用（安全最佳实践）
RUN useradd -m crawler && chown -R crawler:crawler /app
USER crawler

# 暴露端口
EXPOSE 8500

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8500/health')" || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8500", "--workers", "1"]
