# MVP Beta 试用版上线与优化路线

> 版本：v1.0
> 日期：2026-06-03
> 当前定位：MVP Beta 试用版
> 覆盖范围：技术日报系统、自动优化系统、Web Collector、独立 crawler-service、部署链路

## 结论

当前版本已经达到 **MVP Beta 初步上线试用** 条件。适合个人博客管理员小范围真实使用，用真实日报任务继续观察系统质量。

MVP Beta 的目标不是完全自动化的高质量编辑系统，而是先保证：

1. 管理员可以手动触发技术日报。
2. 系统可以自动采集、整理、保存和展示日报。
3. 自动优化系统可以记录质量趋势和弱点建议。
4. Crawler 服务可以作为独立 HTTP 服务供博客和少量内部服务调用。
5. Docker Compose 部署链路具备可复现基础。

## 最近验证基线

验证日期：2026-06-03

| 项目 | 结果 |
| --- | --- |
| Backend 测试 | `mvn test`：75 passed |
| Crawler 测试 | `python -m pytest -q --tb=short`：1266 passed，1 warning |
| Frontend 构建 | `npm run build`：passed |
| Frontend 生产依赖审计 | `npm audit --omit=dev`：0 vulnerabilities |
| Compose 配置 | `docker compose --env-file .env.example config`：passed |
| Frontend Docker build | `docker compose --env-file .env.example build frontend`：passed |

非阻断项：

- Crawler 测试有 1 个 Windows/Python 3.13 event loop warning。
- Frontend dev/build 工具链仍有 5 个中危 audit 项，需要后续大版本升级 Vite/vue-tsc。

## 当前能力边界

### 已具备能力

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 日报触发 | 可用 | 管理端手动触发、强制重新生成 |
| 日报调度 | 可用 | 工作日 8:00 定时生成，受配置开关控制 |
| 信息源采集 | 可用 | keyword/url/rss/mixed section |
| AI 整理 | 可用 | OpenAI-compatible endpoint，试用模型 `deepseek-v4-pro` |
| 结构化保存 | 可用 | `digest_section`、`digest_item`、任务元数据 |
| 公开展示 | 可用 | `/api/digest`、`/api/digest/latest`、`/api/digest/{date}` |
| 管理展示 | 可用 | `/admin/digest`、任务详情、信息源管理 |
| 自动优化 | 初步可用 | 质量评分、趋势、弱点建议、优化记录 |
| 配置中心 | 可用 | Java `sys_config` 下发 crawler/AI/digest/optimization 配置 |
| 独立 crawler-service | 可用 | 支持 API key、任务 API、callback、健康检查 |
| 部署 | 可用 | Compose、Nginx、PostgreSQL、Redis、Backend、Crawler、Frontend |

### 暂不承诺能力

| 能力 | 当前状态 | 说明 |
| --- | --- | --- |
| 完全无人值守高质量日报 | 暂不承诺 | 试用期仍建议人工抽查 |
| 强事实核查 | 暂不承诺 | 当前依赖来源 URL 和 AI 摘要，不做多源交叉验证 |
| 大规模多租户调用 | 暂不承诺 | 当前按博客 + 最多 1 个内部服务设计 |
| 实时资讯监控 | 暂不承诺 | 当前定位为 daily digest |
| 独立 SaaS 平台 | 暂不承诺 | 当前是内部可复用服务，不是商业化平台 |

## 试用上线配置建议

上线前必须配置：

| 配置 | 建议 |
| --- | --- |
| `CRAWLER_API_KEY` | 强随机值 |
| `CRAWLER_CALLBACK_API_KEY` | 强随机值 |
| `BLOG_SECURITY_ENCRYPTION_KEY` | 至少 16 字符强随机值 |
| `AI_API_KEY` | 使用可控试用额度 |
| `AI_BASE_URL` | OpenAI-compatible endpoint |
| `AI_MODEL` | 试用环境当前为 `deepseek-v4-pro` |
| `DIGEST_ENABLED` | 信息源确认后再设为 `true` |
| `CORS_ALLOWED_ORIGINS` | 明确生产域名 |
| `COOKIE_SECURE` | HTTPS 环境设为 `true` |

推荐首批信息源：

| section | 类型 | 建议 |
| --- | --- | --- |
| `hot_trend` | mixed | GitHub Blog RSS、HN RSS、AI/security/developer news keyword |
| `open_source` | url + keyword | GitHub Trending、release、developer tool keyword |
| `tech_article` | keyword/rss | 官方工程博客、InfoQ、高质量技术站点，减少泛化搜索词 |

## 当前已知问题

| 优先级 | 问题 | 影响 | 建议 |
| --- | --- | --- | --- |
| P1 | 外部来源波动 | 日报质量不稳定 | 增加稳定 RSS/官方来源占比 |
| P1 | GitHub Trending 可能出现列表页 URL | 来源可追溯性下降 | 继续强化 repo 级 URL 展开 |
| P1 | `tech_article` 候选可能混入定义页/下载页 | 降低深度 | 增加站点白名单和 generic content penalty |
| P1 | 自动优化建议仍偏轻反馈 | 质量提升速度慢 | 将 weakness 转成下一轮强约束 |
| P2 | 前端 dev audit 仍有中危 | 工具链安全债 | 单独升级 Vite/vue-tsc |
| P2 | Crawler Windows event loop warning | 测试噪音 | 后续按 Python 版本和 TestClient 生命周期优化 |

## Beta 阶段路线

### Beta-1：试用稳定化

目标：让系统连续稳定生成可读、可追溯的日报。

任务：

- 观察连续 3 个工作日自动生成结果。
- 记录失败来源、低质量来源和重复来源。
- 将已完成任务进度统一展示为 `100%`。
- 继续修复 repo 级 URL 展开。
- 优化 `tech_article` 信息源过滤。

验收：

- 连续 3 个工作日生成成功。
- 每期至少 3 个 section 或 6 条有效条目。
- 核心条目均有可访问 source URL。
- 管理端能看到任务状态和失败原因。

### Beta-2：自动优化强反馈

目标：让自动优化真正影响下一轮日报质量。

任务：

- 将 `digest_final_eval` 输出转成 structured action。
- 将低 `language_coverage` 转成跨语言补采约束。
- 将重复来源建议转成输出前强去重约束。
- 将 `tech_article` 质量问题转成白名单/黑名单策略。

验收：

- 连续两次日报中，同类弱点不应重复出现而无策略变化。
- 趋势接口能展示策略调整原因。
- 测试覆盖“最终评估 -> 下一轮计划”的闭环。

### Beta-3：独立服务接入增强

目标：让 crawler-service 稳定服务博客以外的第二个内部服务。

任务：

- 完善 API key 使用说明。
- 明确 callback payload 和错误码。
- 补充 client 接入文档。
- 梳理 `/api/v1/tasks` 和 `/api/v1/digests/*` 兼容性说明。

验收：

- 新服务只需 base URL + API key 即可创建任务并轮询结果。
- callback 可选，不影响任务完成。
- 博客仍作为普通 client 正常工作。

### Beta-4：运维与观测

目标：降低试用期排查成本。

任务：

- 增加日报任务 trace id。
- 增加最近失败来源列表。
- 增加 scheduler 状态面板。
- 增加每日生成结果健康摘要。

验收：

- 管理员能在 3 分钟内判断失败原因属于 AI、搜索、源站、配置还是回调。

## MVP Beta 通过标准

满足以下条件，可认为试用版达到预期：

1. 连续 3 个工作日自动生成日报。
2. 每期日报至少包含 3 个 section 或不少于 6 条有效条目。
3. 每条核心条目有可访问 source URL。
4. 日报失败时管理端能看到失败状态和错误信息。
5. 优化趋势持续记录，并能解释主要质量问题。

如果连续 2 天出现空日报、明显重复、严重幻觉或 AI 不可用，应暂停自动发布，改为管理员手动触发和审查。
