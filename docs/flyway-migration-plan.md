# Flyway 接入方案（B15-04）

> 状态：**代码/配置就绪，启用待真实环境验证**
> 背景：审计 B15-04 发现 Flyway 完全未集成（pom 无依赖、yml 无配置、23 个 migration 脚本不执行），schema 三轨（schema.sql / init.sql / V1_1~V1_23）漂移。本方案完成接入准备，实际启用是运维步骤（需真实 PG 验证 baseline）。

## 已完成的准备

1. **pom.xml**：加 `flyway-core` + `flyway-database-postgresql`（Spring Boot 3.3.5 管理 Flyway 10.x）
2. **application.yml**：加 `spring.flyway`（**enabled=false 默认不启用**，baseline-on-migrate + baseline-version=1.0.23 + validate-on-migrate=false + locations）
3. **V1_24__add_task_python_id_index.sql**：补 schema.sql 漂移（idx_task_python_id，V1_19 引入但 schema.sql 缺）

## baseline 策略

- `baseline-version: 1.0.23`：现有库（schema.sql 建的）被认作 V1.0.23 基线，Flyway **不重跑** V1_1~V1_23（避免与已建表冲突）
- `baseline-on-migrate: true`：非空库首次启动时自动 baseline
- `validate-on-migrate: false`：容忍 V1_1~V1_23 与 schema.sql 的历史漂移（baseline 不执行它们，不校验 checksum）
- 后续 schema 变更用 V1_25+ 增量 migration

## 启用步骤（运维，必须在预发验证）

1. **预发建库**：`docker compose up postgres`，确认 schema.sql 建库成功（含全部表）
2. **flip enabled**：预发 `SPRING_FLYWAY_ENABLED=true`（或 application-prod.yml）
3. **启动 backend**，确认：
   - Flyway 日志：`Successfully baselined schema with version 1.0.23`
   - Flyway 日志：`Migrating schema to version 1.24`（执行 V1_24 补 idx_task_python_id）
   - **不**出现 V1_1~V1_23 的执行（baseline 跳过）
   - 应用启动成功
4. **业务验证**：日报/采集/文章主链路正常
5. **生产 flip**：预发全绿后，生产 `SPRING_FLYWAY_ENABLED=true`

## 风险与回退

- **风险**：baseline-version 与 schema.sql 实际状态不匹配 → V1_24+ 可能漏补或多补。预发验证 V1_24 索引确实创建。
- **回退**：`SPRING_FLYWAY_ENABLED=false` 即停用 Flyway，schema.sql 仍是建库机制（现状不变）。

## 三轨漂移的后续清理（启用 Flyway 后）

启用 Flyway 后，schema.sql 仍用于 Docker 首次建卷（postgres init-scripts）。为彻底消除双轨：
- 长期：把 schema.sql 的建表逻辑收敛到 Flyway baseline（V1_0__baseline.sql），Docker 不再用 schema.sql
- 短期：保持 schema.sql 为建库、Flyway 为增量，每次新增 migration 同步更新 schema.sql（或接受 Flyway 为唯一演进源，schema.sql 仅 fresh init）

## 未覆盖（仍需处理）

- B15-06 config seed 三轨漂移（init.sql/schema.sql 仍 seed V1_21 删的 64 项）：启用 Flyway 后，新 migration 清理 seed，或 admin 手动清
- init.sql 与 schema.sql 的其他差异（ai_generation 表等）：以 schema.sql（生产基线）为准，init.sql 逐步废弃
