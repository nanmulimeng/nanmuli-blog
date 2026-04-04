# 数据库配置目录

## 目录结构

```
db/
├── init-scripts/          # 数据库初始化脚本
│   └── schema.sql        # 数据库Schema（表结构、索引、外键、初始数据）
└── README.md             # 本文件
```

## 说明

- `init-scripts/schema.sql` - 数据库初始化脚本，包含：
  - 创建表结构
  - 创建索引
  - 添加外键约束
  - 插入初始数据（管理员账号、默认分类、标签等）

## 初始化流程

Docker Compose 启动时会自动执行 `init-scripts` 目录下的 `.sql` 文件：

1. 首次启动 PostgreSQL 容器时
2. 数据卷为空时

## 手动执行

如需手动初始化数据库：

```bash
# 进入 PostgreSQL 容器
docker-compose exec postgres psql -U postgres -d nanmuli_blog

# 执行SQL脚本
\i /docker-entrypoint-initdb.d/schema.sql
```

## 备份与恢复

```bash
# 备份
docker-compose exec postgres pg_dump -U postgres nanmuli_blog > backup.sql

# 恢复
docker-compose exec -T postgres psql -U postgres nanmuli_blog < backup.sql
```
