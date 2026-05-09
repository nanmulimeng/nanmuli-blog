"""SSRF 防护 — 私有地址校验依赖

注意：此模块仅在 DNS 解析前检查 hostname 的 IP 归属。
DNS rebinding 攻击（TOCTOU）在此层面无法完全防御，
完整防护需要网络层（如 iptables 规则或 SOCKS 代理过滤）。
此处的检查作为应用层的基本防护层。
"""

import ipaddress
from urllib.parse import urlparse

from fastapi import HTTPException

# URL hostname 长度上限（防止超长 URL 攻击，RFC 1034 建议域名不超过 253 字符）
_MAX_HOSTNAME_LENGTH = 253


def _is_private_url(url: str) -> bool:
    """检查 URL 是否指向内网/私有地址（SSRF 防护）"""
    try:
        parsed = urlparse(str(url))
        hostname = parsed.hostname
        if not hostname:
            return False

        # hostname 长度限制（防止超长 URL 攻击）
        if len(hostname) > _MAX_HOSTNAME_LENGTH:
            return True

        # 去除 IPv6 方括号
        if hostname.startswith("[") and hostname.endswith("]"):
            hostname = hostname[1:-1]
        # 常见内网域名
        if hostname in ("localhost", "localhost.localdomain") or hostname.endswith(".local"):
            return True
        # IP 地址检查
        try:
            ip = ipaddress.ip_address(hostname)
            # 检查私有/回环/链路本地/保留地址
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
            # 特殊地址：0.0.0.0 和 [::]（绑定所有接口，常被滥用于 SSRF）
            if hostname in ("0.0.0.0", "::", "[::]"):
                return True
            return False
        except ValueError:
            pass  # 非 IP 的域名，放行
        return False
    except Exception:
        return False


def validate_url_ssrf(url: str) -> str:
    """FastAPI 兼容的 SSRF 校验函数，用于在端点内调用。

    如果 URL 指向私有地址，抛出 400 HTTPException。
    返回原始 URL 字符串。
    """
    if _is_private_url(str(url)):
        raise HTTPException(status_code=400, detail="不允许爬取内网/私有地址")
    return str(url)
