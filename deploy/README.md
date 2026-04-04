# Nanmuli Blog 部署指南

## 目录结构

```
deploy/
├── backend/                    # 后端部署配置
│   ├── Dockerfile              # 后端服务 Docker 镜像构建文件
│   ├── application.yml         # 主配置文件
│   ├── application-dev.yml     # 开发环境配置
│   └── application-prod.yml    # 生产环境配置
├── nginx/                      # Nginx 配置
│   ├── nginx.conf              # Nginx 主配置
│   └── conf.d/
│       └── default.conf        # 站点配置
├── db/                         # 数据库配置
│   ├── init-scripts/
│   │   └── schema.sql          # 数据库初始化脚本
│   └── README.md               # 数据库配置说明
├── docker-compose.yml          # Docker 编排文件
├── .env.example                # 环境变量示例
└── README.md                   # 本文件
```

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，设置数据库密码等敏感信息
```

### 2. 构建并启动服务

```bash
# 构建前端（在 frontend 目录执行）
cd ../frontend
npm run build

# 构建并启动所有服务（在 deploy 目录执行）
cd ../deploy
docker-compose up -d
```

### 3. 初始化数据库

```bash
# 进入 PostgreSQL 容器执行初始化脚本
docker-compose exec postgres psql -U postgres -d nanmuli_blog -f /docker-entrypoint-initdb.d/schema.sql
```

## 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx | 80/443 | 前端静态资源 + 反向代理 |
| Backend | 8080 | Spring Boot 后端服务 |
| PostgreSQL | 5432 | 主数据库 |
| Redis | 6379 | 缓存/会话 |

## 常用命令

```bash
# 查看日志
docker-compose logs -f backend
docker-compose logs -f nginx

# 重启服务
docker-compose restart backend

# 停止所有服务
docker-compose down

# 停止并删除数据卷（谨慎使用）
docker-compose down -v
```

## 生产环境配置

1. 修改 `.env` 中的密码为强密码
2. 配置 SSL 证书（放置于 `ssl/` 目录）
3. 修改 `application-prod.yml` 中的配置
4. 启用防火墙，只开放 80/443 端口
5. 配置自动备份策略

## 注意事项

- 首次启动时会自动初始化数据库
- 文件上传目录挂载为 `/uploads`
- 日志文件可通过 `docker-compose logs` 查看
