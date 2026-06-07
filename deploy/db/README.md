# Database Deployment Notes

> 更新时间：2026-06-03
> 适用版本：MVP Beta 试用版

`deploy/db` 存放 Docker Compose 首次启动 PostgreSQL 时执行的初始化脚本。生产或长期试用环境建议优先使用后端 Flyway migration 管理结构演进，`init-scripts` 更适合全新环境的一次性初始化。

## 目录结构

```text
deploy/db/
├── init-scripts/
│   └── schema.sql
└── README.md
```

## 初始化行为

PostgreSQL 官方镜像只会在数据目录为空时执行 `/docker-entrypoint-initdb.d` 下的脚本。

这意味着：

- 首次创建数据库卷时会执行 `schema.sql`。
- 已存在数据卷时不会重复执行。
- 后续结构变更应通过后端 `src/main/resources/db/migration` 下的 Flyway 脚本完成。

## MVP Beta 数据要求

试用版至少需要以下数据能力：

- 文章、分类、技术日志、项目、技能、友链、文件、用户。
- 系统配置 `sys_config`。
- Web 采集任务、采集结果、日报结果。
- 日报质量评分、质量趋势、自动优化记录。
- Crawler 依赖模式、API Key、AI endpoint、日报参数等配置项。

## 常用命令

进入数据库：

```bash
docker compose exec postgres psql -U postgres -d nanmuli_blog
```

备份：

```bash
docker compose exec postgres pg_dump -U postgres nanmuli_blog > backup.sql
```

恢复：

```bash
docker compose exec -T postgres psql -U postgres nanmuli_blog < backup.sql
```

查看 Flyway 版本：

```sql
select installed_rank, version, description, success
from flyway_schema_history
order by installed_rank desc;
```

## 上线注意事项

- 不要在已有生产数据卷上依赖 `schema.sql` 自动补结构。
- 修改数据库前先备份。
- 新增配置项优先走 Flyway + `SystemConfigInitializer` 双保险。
- 涉及日报和自动优化的表结构变化，要同步检查 crawler-service 的 API contract。
