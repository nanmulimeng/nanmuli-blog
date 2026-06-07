# Documentation Index

> 更新时间：2026-06-03  
> 当前项目状态：MVP Beta 试用版

本目录分为两类文档：项目当前状态文档和外部技术参考文档。判断项目现状、上线范围和未来计划时，以“项目当前状态文档”为准。

## 项目当前状态文档

| 文档 | 说明 |
|------|------|
| `../README.md` | 项目总览、启动方式、验证基线、MVP 结论 |
| `trial-release-roadmap.md` | MVP Beta 试用上线范围、检查清单、阶段路线图 |
| `future-development-plan.md` | 未来开发计划和优先级 |
| `digest-system.md` | 日报生成系统与自动优化系统说明 |
| `web-collector-module-design.md` | WebCollector 当前架构与功能边界 |
| `config-db-migration-plan.md` | 配置同步、数据库迁移、上线注意事项 |
| `plan-crawl-tools-refactor.md` | 爬虫工具层后续重构参考计划 |
| `../crawler-service/README.md` | Crawler Service 独立服务说明 |
| `../crawler-service/docs/architecture-v3.md` | Crawler Service v3 架构说明 |
| `../crawler-service/docs/daily-digest-review.md` | 日报质量评审与后续改进 |
| `../deploy/README.md` | Docker Compose 部署说明 |
| `../deploy/db/README.md` | 数据库部署说明 |
| `../frontend/README.md` | 前端项目说明 |
| `../deploy/docs/ui-design.md` | UI 设计参考 |
| `../deploy/docs/color-schemes.md` | 配色参考 |

## 外部技术参考文档

以下文档用于开发参考，不代表当前项目状态：

| 文档 | 说明 |
|------|------|
| `spring_ai_1.1.4_tutorial_supplemented.md` | Spring AI 参考资料 |
| `postgresql_tutorial_supplemented.md` | PostgreSQL 参考资料 |
| `postgresql_pgvector_tutorial_supplemented.md` | PostgreSQL pgvector 参考资料 |
| `Crawl4AI/README.md` | Crawl4AI 资料入口 |
| `Crawl4AI/Crawl4AI完整使用文档.md` | Crawl4AI 使用文档 |
| `Crawl4AI/crawl4ai_quick_reference.md` | Crawl4AI 快速参考 |
| `Crawl4AI/crawl4ai_config_guide.md` | Crawl4AI 配置参考 |

## MVP Beta 当前结论

截至 2026-06-03，项目可以进入初步试用上线阶段。试用范围包括博客基础功能、管理端配置、Web 采集器、日报生成系统和自动优化轻闭环。

当前不承诺：

- 标签系统完整上线。
- 大规模多租户 crawler 平台。
- 完全无人值守的高质量日报长期稳定输出。
- 所有外部信息源永久稳定。

## 文档维护规则

- 项目状态变化优先更新 `README.md`、`trial-release-roadmap.md` 和 `future-development-plan.md`。
- 日报或自动优化逻辑变化同步更新 `digest-system.md`。
- Crawler API 或部署方式变化同步更新 `crawler-service/README.md` 和 `web-collector-module-design.md`。
- 数据库或配置项变化同步更新 `config-db-migration-plan.md` 和 `deploy/db/README.md`。
- 外部参考文档只在版本升级或内容明显失效时更新。
