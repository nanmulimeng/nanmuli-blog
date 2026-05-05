# 自定义 PostgreSQL 镜像: pgvector + zhparser 中文分词
# 基础镜像: ankane/pgvector (基于 postgres:16)
# 编译安装:
#   - SCWS 1.2.3 (zhparser 依赖的中文分词库)
#   - zhparser 2.2 (PostgreSQL 中文 FTS 扩展)
#
# 构建: docker compose build postgres
# 大小影响: 约 +30MB (清理 apt 缓存与构建工具后)

FROM ankane/pgvector:latest

USER root

ARG SCWS_VERSION=1.2.3
ARG ZHPARSER_VERSION=2.2

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        autoconf \
        automake \
        libtool \
        locales \
        ca-certificates \
        curl \
        "postgresql-server-dev-${PG_MAJOR}"; \
    \
    # 确保 en_US.UTF-8 locale 可用(兼容旧数据目录的 postgresql.conf)
    sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && locale-gen; \
    \
    # 1. 编译安装 SCWS
    # GitHub 自动生成的 tarball 不含 configure 脚本,需先执行 autoreconf
    cd /tmp; \
    curl -fsSL "https://github.com/hightman/scws/archive/refs/tags/${SCWS_VERSION}.tar.gz" -o scws.tar.gz; \
    tar xzf scws.tar.gz; \
    cd "scws-${SCWS_VERSION}"; \
    autoreconf -fi; \
    ./configure --prefix=/usr/local; \
    make -j"$(nproc)"; \
    make install; \
    \
    # 2. 编译安装 zhparser
    cd /tmp; \
    curl -fsSL "https://github.com/amutu/zhparser/archive/refs/tags/V${ZHPARSER_VERSION}.tar.gz" -o zhparser.tar.gz; \
    tar xzf zhparser.tar.gz; \
    cd "zhparser-${ZHPARSER_VERSION}"; \
    SCWS_HOME=/usr/local make USE_PGXS=1; \
    SCWS_HOME=/usr/local make USE_PGXS=1 install; \
    \
    # 3. 清理构建工具与临时文件
    apt-get purge -y --auto-remove \
        build-essential \
        autoconf \
        automake \
        libtool \
        curl \
        "postgresql-server-dev-${PG_MAJOR}"; \
    rm -rf /tmp/* /var/lib/apt/lists/*

USER postgres
