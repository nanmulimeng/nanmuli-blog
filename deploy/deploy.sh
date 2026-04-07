#!/bin/bash

# Nanmuli Blog 部署脚本
# 支持本地构建部署和 Docker 部署

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Nanmuli Blog 部署脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查命令
command -v docker >/dev/null 2>&1 || { echo -e "${RED}错误: 需要 Docker 但未安装${NC}"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}错误: 需要 Docker Compose 但未安装${NC}"; exit 1; }

# 部署模式选择
echo "请选择部署模式:"
echo "1) Docker Compose 完整部署（推荐）"
echo "2) 仅部署爬虫服务"
echo "3) 停止所有服务"
echo "4) 查看服务状态"
echo ""
read -p "请输入选项 [1-4]: " choice

case $choice in
    1)
        echo -e "${YELLOW}开始 Docker Compose 完整部署...${NC}"

        # 创建必要目录
        mkdir -p uploads logs

        # 拉取最新镜像并启动
        docker-compose -f docker-compose.yml pull
        docker-compose -f docker-compose.yml up -d --build

        echo ""
        echo -e "${GREEN}========================================${NC}"
        echo -e "${GREEN}  部署完成!${NC}"
        echo -e "${GREEN}========================================${NC}"
        echo ""
        echo "服务访问地址:"
        echo "  - PostgreSQL: localhost:5433"
        echo "  - Redis: localhost:6380"
        echo "  - 爬虫服务: http://localhost:8500"
        echo ""
        echo "查看日志:"
        echo "  docker-compose -f docker-compose.yml logs -f [service_name]"
        echo ""
        echo "停止服务:"
        echo "  docker-compose -f docker-compose.yml down"
        ;;

    2)
        echo -e "${YELLOW}开始部署爬虫服务...${NC}"

        cd ../crawler-service
        docker build -t nanmuli-crawler:latest .

        # 停止旧容器
        docker stop nanmuli-crawler 2>/dev/null || true
        docker rm nanmuli-crawler 2>/dev/null || true

        # 启动新容器
        docker run -d \
            --name nanmuli-crawler \
            -p 8500:8500 \
            -e PORT=8500 \
            -e MAX_PAGES_DEFAULT=10 \
            -e LOG_LEVEL=INFO \
            --restart unless-stopped \
            nanmuli-crawler:latest

        echo -e "${GREEN}爬虫服务部署完成!${NC}"
        echo "访问: http://localhost:8500/docs"
        ;;

    3)
        echo -e "${YELLOW}停止所有服务...${NC}"
        docker-compose -f docker-compose.yml down
        echo -e "${GREEN}服务已停止${NC}"
        ;;

    4)
        echo -e "${YELLOW}服务状态:${NC}"
        docker-compose -f docker-compose.yml ps
        echo ""
        echo -e "${YELLOW}资源使用:${NC}"
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.Status}}"
        ;;

    *)
        echo -e "${RED}无效选项${NC}"
        exit 1
        ;;
esac
