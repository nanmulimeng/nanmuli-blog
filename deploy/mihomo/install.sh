#!/bin/bash
# ============================================
# Mihomo 代理一键安装脚本
# 适用：Debian/Ubuntu/CentOS (amd64/arm64)
# 安装到服务器后爬虫即可通过 127.0.0.1:7890 访问外网
# ============================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ---- 配置 ----
INSTALL_DIR="/opt/mihomo"
BIN_PATH="/usr/local/bin/mihomo"
CONFIG_DIR="/etc/mihomo"
SERVICE_NAME="mihomo"

# ---- 检查 ----
if [[ "$(uname -s)" != "Linux" ]]; then
    echo -e "${RED}错误: 此脚本仅支持 Linux 服务器${NC}"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}错误: 需要 root 权限运行${NC}"
    echo "请使用: sudo bash install.sh"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Mihomo 代理安装脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ---- 架构检测 ----
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  MIHOMO_ARCH="amd64"    ;;
    aarch64) MIHOMO_ARCH="arm64"    ;;
    arm64)   MIHOMO_ARCH="arm64"    ;;
    armv7l)  MIHOMO_ARCH="armv7"    ;;
    *)
        echo -e "${RED}错误: 不支持的架构: $ARCH${NC}"
        exit 1
        ;;
esac
echo -e "${GREEN}[1/5]${NC} 检测到架构: ${YELLOW}$ARCH${NC} → mihomo-${MIHOMO_ARCH}"

# ---- 订阅 URL ----
echo ""
echo -e "${YELLOW}请输入代理订阅 URL（如 https://sub.example.com/link/xxx）${NC}"
echo -e "${YELLOW}没有订阅直接回车，后续手动编辑 ${CONFIG_DIR}/config.yaml 添加静态节点${NC}"
read -rp "订阅 URL: " SUBSCRIPTION_URL
echo ""

if [[ -n "$SUBSCRIPTION_URL" ]]; then
    echo -e "${GREEN}[2/5]${NC} 订阅模式: ${SUBSCRIPTION_URL}"
else
    echo -e "${YELLOW}[2/5]${NC} 静态节点模式: 跳过订阅，请稍后手动编辑配置"
fi

# ---- 下载 mihomo ----
echo -e "${GREEN}[3/5]${NC} 下载 Mihomo 二进制..."

# 获取最新版本号
LATEST_VERSION=$(curl -fsSL "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest" \
    | grep -oP '"tag_name":\s*"v\K[^"]+' || echo "")

if [[ -z "$LATEST_VERSION" ]]; then
    echo -e "${RED}错误: 无法获取版本信息，请检查网络${NC}"
    exit 1
fi

echo "最新版本: v${LATEST_VERSION}"

DOWNLOAD_URL="https://github.com/MetaCubeX/mihomo/releases/download/v${LATEST_VERSION}/mihomo-linux-${MIHOMO_ARCH}-v${LATEST_VERSION}.gz"

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 下载并校验
if ! curl -fsSL -m 120 -o mihomo.gz "$DOWNLOAD_URL"; then
    echo -e "${RED}错误: 下载失败${NC}"
    echo "手动下载: $DOWNLOAD_URL"
    exit 1
fi

gunzip -f mihomo.gz
chmod +x mihomo
cp -f mihomo "$BIN_PATH"

echo -e "${GREEN}  ✓ Mihomo v${LATEST_VERSION} 安装到 ${BIN_PATH}${NC}"

# ---- 生成配置 ----
echo -e "${GREEN}[4/5]${NC} 生成配置文件..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/config.template.yaml"

if [[ ! -f "$TEMPLATE" ]]; then
    echo -e "${RED}错误: 找不到配置模板 $TEMPLATE${NC}"
    exit 1
fi

mkdir -p "$CONFIG_DIR"
mkdir -p "${INSTALL_DIR}/providers"

if [[ -n "$SUBSCRIPTION_URL" ]]; then
    # 订阅模式：替换占位符
    sed "s|{{SUBSCRIPTION_URL}}|${SUBSCRIPTION_URL}|g" "$TEMPLATE" > "${CONFIG_DIR}/config.yaml"
else
    # 静态节点模式：移除 proxy-providers，改用空节点
    sed '/^proxy-providers:/,/^$/{
        /^proxy-providers:/d
        /^  sub:/d
        /^    type:/d
        /^    url:/d
        /^    interval:/d
        /^    path:/d
        /^    health-check:/d
        /^      enable:/d
        /^      url:/d
        /^      interval:/d
        /^$/d
    }' "$TEMPLATE" > "${CONFIG_DIR}/config.yaml"
    # 移除 proxy-groups 中的 use 引用
    sed -i 's/^    use:/    # use:/' "${CONFIG_DIR}/config.yaml"
    sed -i 's/^      - sub/    #   - sub/' "${CONFIG_DIR}/config.yaml"
fi

echo -e "${GREEN}  ✓ 配置写入 ${CONFIG_DIR}/config.yaml${NC}"

# ---- 注册 systemd 服务 ----
echo -e "${GREEN}[5/5]${NC} 注册 systemd 服务..."

cat > /etc/systemd/system/${SERVICE_NAME}.service << SERVICE_EOF
[Unit]
Description=Mihomo Proxy (Clash Meta)
Documentation=https://wiki.metacubex.one/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=${BIN_PATH} -d ${CONFIG_DIR}
Restart=on-failure
RestartSec=5s
LimitNOFILE=65536

# 内存限制（2GB 服务器友好）
MemoryMax=128M
CPUQuota=50%

# 工作目录（存放 GeoIP/GeoSite 数据库、providers）
WorkingDirectory=${CONFIG_DIR}

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}" 2>/dev/null || true
systemctl start "${SERVICE_NAME}" 2>/dev/null || true

sleep 2

# ---- 验证 ----
echo ""
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✓ Mihomo 安装成功!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "代理地址: http://127.0.0.1:7890"
    echo "控制面板: http://127.0.0.1:9090"
    echo ""
    echo "常用命令:"
    echo "  systemctl status mihomo   # 查看状态"
    echo "  systemctl restart mihomo  # 重启"
    echo "  journalctl -u mihomo -f   # 查看日志"
    echo "  vim /etc/mihomo/config.yaml  # 编辑配置"
    echo ""
    echo -e "${YELLOW}爬虫 .env 中设置: PROXY_URL=http://127.0.0.1:7890${NC}"
    echo ""
    # 快速连通性测试
    echo "代理连通性测试..."
    if curl -fsSL -m 5 -x http://127.0.0.1:7890 https://www.google.com -o /dev/null 2>/dev/null; then
        echo -e "${GREEN}  ✓ 代理访问 Google 正常${NC}"
    else
        echo -e "${YELLOW}  ⚠ 代理已启动但访问 Google 失败，可能是订阅节点问题${NC}"
        echo "  查看日志: journalctl -u mihomo -n 20"
    fi
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  ✗ Mihomo 启动失败${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "排查步骤:"
    echo "  journalctl -u mihomo -n 30"
    echo "  ${BIN_PATH} -d ${CONFIG_DIR} -t  # 测试配置"
    exit 1
fi
