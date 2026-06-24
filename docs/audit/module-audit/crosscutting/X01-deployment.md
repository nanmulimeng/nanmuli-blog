# X01 部署架构排查报告

> **模块编号**：X01
> **排查范围**：Docker Compose 编排（5 服务）、健康检查、资源限额、启动顺序、网络、数据卷、nginx 反代、各 Dockerfile、镜像基线、mihomo 代理、secrets 管理
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（`deploy/README.md` 已改，属本模块；其余未提交改动在 backend/crawler/docs，不属本模块直接范围）。本模块关键文件 `docker-compose.yml`、`nginx*`、各 `Dockerfile`、`.env.example`、`deploy.sh` **均未在工作区改动中**，基线即当前磁盘内容。
> **排查日期**：2026-06-24
> **排查人**：X01 部署架构排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：用 Docker Compose 把 frontend（nginx 静态 + 反代）、backend（Spring Boot）、crawler（FastAPI/Playwright）、postgres（自建 pgvector+zhparser）、redis 五服务编排成一个可一键启动的 MVP Beta 部署单元，并配套宿主机 mihomo 代理与 deploy.sh/release-gate 上线闸门。

**关键文件**：
- `deploy/docker-compose.yml:1-163` —— 5 服务编排、健康检查、资源限额、depends_on healthy、网络、卷
- `deploy/nginx.conf:1-66` —— **前端容器实际使用的** nginx server 块（被 frontend Dockerfile 复制为 conf.d/default.conf）
- `deploy/nginx/nginx.conf:1-52` —— nginx http 块主配置（含 limit_req_zone 限流），**未被任何 Dockerfile 引用**（死代码）
- `deploy/nginx/conf.d/default.conf:1-61` —— 与 `deploy/nginx.conf` 几乎重复的 server 块
- `backend/Dockerfile:1-43` —— 多阶段构建，ENV JAVA_OPTS 与 compose JAVA_TOOL_OPTIONS 冲突
- `crawler-service/Dockerfile:1-32` —— 基于 playwright:v1.59-jammy，非 root 运行
- `frontend/Dockerfile:1-18` —— node:20-alpine 构建 + nginx:1.27-alpine 运行，**无 HEALTHCHECK**
- `deploy/db/Dockerfile:1-62` —— 自建 pgvector+zhparser，`ankane/pgvector:latest` **未固定 tag**
- `deploy/.env.example:1-49`、`deploy/deploy.sh:1-132`、`deploy/mihomo/{config.template.yaml,install.sh}`
- `deploy/db/init-scripts/schema.sql:1-1170` —— 首次初始化 schema
- `backend/src/main/resources/application-prod.yml:68` —— `blog.file.upload-path: /opt/nanmuli-blog/uploads`
- `backend/src/main/resources/logback-spring.xml:36,56` —— 日志路径 `/opt/nanmuli-blog/logs/`

**对外接口 / 依赖**：
- 对外：宿主机端口 `80`(frontend)/`8081`(backend)/`8500`(crawler)/`5433`(postgres)/`6380`(redis)
- 依赖：Docker Engine + Compose v2、mihomo（宿主机 systemd）、外部 AI provider、PG 镜像生态（pgvector/zhparser/scws 源码编译）

**已读文件清单**：
- `deploy/docker-compose.yml` —— 通读
- `deploy/nginx.conf`、`deploy/nginx/nginx.conf`、`deploy/nginx/conf.d/default.conf` —— 通读
- `backend/Dockerfile`、`crawler-service/Dockerfile`、`frontend/Dockerfile`、`deploy/db/Dockerfile` —— 通读
- `deploy/.env.example`、`deploy/deploy.sh`、`deploy/README.md`、`deploy/db/README.md` —— 通读
- `deploy/mihomo/config.template.yaml`、`deploy/mihomo/install.sh`（head） —— 通读/片段
- `backend/src/main/resources/application-prod.yml`、`application.yml`、`logback-spring.xml`（grep） —— 通读/grep
- `crawler-service/config.py`、`standalone/db.py`（grep） —— grep
- `scripts/release/release-gate.ps1`、`scripts/release/check-deploy-env.ps1`（grep） —— 通读/grep
- `deploy/db/init-scripts/schema.sql` —— grep（CREATE EXTENSION/行数）

**主模块归属**：本模块深查部署架构。对以下共享对象**只引用**：schema.sql 结构（主 B15/X02）、SSRF 网络防护（C01-04）、Cookie/CSRF（B06）、AES 加密 key（B07）、env 三处一致性（X06）、CrawlerTaskClient（B10）。本报告聚焦部署编排本身的正确性与可运维性。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：compose 编排、Dockerfile、路径/卷/端口/健康检查/启动顺序的一致性。逐项核对 compose 声明 vs Dockerfile vs 应用配置 vs 实际语义。

### [P1] [Bug] prod 上传路径与日志路径三处不一致，卷挂载失效   <!-- 编号：X01-01 -->
- **定位**：
  - `backend/src/main/resources/application-prod.yml:68` —— `upload-path: /opt/nanmuli-blog/uploads`
  - `backend/src/main/resources/logback-spring.xml:36,56` —— 日志写到 `/opt/nanmuli-blog/logs/`
  - `backend/Dockerfile:29` —— `RUN mkdir -p /app/uploads /app/logs`
  - `deploy/docker-compose.yml:75-76` —— `backend_uploads:/app/uploads`、`backend_logs:/app/logs`
- **现象**：容器以 `SPRING_PROFILES_ACTIVE=prod` 启动（compose:59），应用读取的 `blog.file.upload-path` 是 `/opt/nanmuli-blog/uploads`，logback 写 `/opt/nanmuli-blog/logs/`。但 Dockerfile 只创建了 `/app/uploads /app/logs`，compose 卷也只挂到 `/app/uploads`、`/app/logs`。`/opt/nanmuli-blog/` 目录在镜像里**不存在**。
- **影响**：①文件上传在首次写入时因父目录不存在抛异常（或由 Spring 的 `Files.createDirectories` 兜底创建在容器可写层，但**卷未覆盖该路径**），上传图片/附件随容器销毁丢失，`docker compose down && up` 后历史文章图片 404；②日志同理不进 `backend_logs` 卷，`docker compose logs` 与卷内日志双轨，排障时卷里是空的；③与 README "管理端可上传文件、日志可查" 的 MVP 承诺矛盾。
- **根因/分析**：三套路径在不同时期写入，未对齐。`application.yml:59` 默认 `./uploads`（相对 WORKDIR=/app 即 /app/uploads，与卷一致），但 prod profile 覆盖成了 `/opt/nanmuli-blog/uploads`，疑似从"裸机部署"遗留。logback 同样写死 `/opt/nanmuli-blog/logs/`。已排除"卷以相对路径挂载"——compose 用的是命名卷 + 绝对容器路径。
- **修复方向**：
  1. 统一路径：`application-prod.yml` 改 `upload-path: /app/uploads`，logback 改 `/app/logs/`（改动面：小，单配置文件，但涉及运行时数据迁移）
  2. 或反过来：Dockerfile 改 `mkdir /opt/nanmuli-blog/{uploads,logs}` + compose 卷改挂该路径（改动面：中，需同步改两处）
  3. 推荐①，与 `application.yml` 默认值对齐，最小变动。**迁移注意**：已存在的上传文件需从容器可写层拷出再迁入卷。
- **关联**：次维度 [Arch]（配置漂移）；横向主题"配置一致性"归 X06；文件上传安全细节归 B05。

### [P2] [Bug] nginx 限流主配置是死代码，线上零限流   <!-- 编号：X01-02 -->
- **定位**：
  - `deploy/nginx/nginx.conf:48-49` —— `limit_req_zone ... zone=api_limit:10m rate=10r/s;` `zone=login_limit:10m rate=1r/s;`
  - `frontend/Dockerfile:15` —— `COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf`（只复制 server 块，**不复制** `deploy/nginx/nginx.conf` 这个 http 块主配置）
  - `deploy/nginx.conf:37-45` —— 实际生效的 server 块里**没有** `limit_req` 指令
- **现象**：仓库里有两份看起来都"像 nginx 配置"的文件：`deploy/nginx.conf`（server 块，被用）和 `deploy/nginx/nginx.conf`（http 块主配置，含 gzip/limit_req_zone/client_max_body_size 50M，**未被任何 Dockerfile 引用**）。frontend 镜像实际用的是 nginx 官方镜像自带的 `/etc/nginx/nginx.conf` 默认主配置 + 复制进去的 `deploy/nginx.conf` 作为 `conf.d/default.conf`。因此 `deploy/nginx/nginx.conf` 里定义的 `api_limit`/`login_limit` 限流 zone **从未被加载**，server 块里也没有任何 `limit_req` 引用。
- **影响**：①登录接口、API 全路径无 nginx 层限流，爆破登录、CC 攻击只能靠 backend Sa-Token 限流（见 B06）兜底，单点防护；②`deploy/README.md:25-26` 把 `nginx/conf.d/default.conf` 标为"可选 Nginx 站点配置"，掩盖了主配置未生效的事实，误导维护者以为限流在跑；③`client_max_body_size` 用 nginx 默认 1M，而 backend 文件上传白名单含 zip/rar/pdf（B05），**>1M 上传会被 nginx 413 拦截**（应用层允许但网关层拒）。
- **根因/分析**：历史演进遗留——早期可能用 `deploy/nginx/nginx.conf` 作主配置，后改为直接 `COPY deploy/nginx.conf`，旧文件未清理。`deploy/nginx/conf.d/default.conf` 与 `deploy/nginx.conf` 内容近乎重复（只差一个 `/crawler-health` location），进一步说明是迁移半成品。已排除"compose 用 volume 挂载 nginx.conf"——compose 中 frontend 无 volume 挂载。
- **修复方向**：
  1. 若要启用限流：frontend Dockerfile 增加 `COPY deploy/nginx/nginx.conf /etc/nginx/nginx.conf`（覆盖镜像默认），并在 server 块加 `limit_req zone=api_limit burst=...; limit_req zone=login_limit burst=...;`，同时确认 `client_max_body_size 50M` 生效（改动面：中，需重新构建镜像 + 压测 burst 值）
  2. 若不启用：删除 `deploy/nginx/nginx.conf` 与 `deploy/nginx/conf.d/default.conf`，更新 README 说明限流由 backend 负责（改动面：小，纯清理）
  3. 推荐先做②消除歧义，再按真实流量决定是否补①。
- **关联**：次维度 [Security]（限流缺失）；B06（Sa-Token 限流）、B10（digest 接口限流建议引用此条）。

### [P2] [Bug] crawler 容器无法访问宿主机 mihomo 代理   <!-- 编号：X01-03 -->
- **定位**：
  - `deploy/mihomo/config.template.yaml:7,10-11` —— mihomo 监听 `127.0.0.1:7890`，`allow-lan: false`
  - `deploy/docker-compose.yml:120` —— crawler 注入 `PROXY_URL: ${PROXY_URL:-}`，**无 `extra_hosts`/`network_mode: host`**
  - `deploy/docker-compose.yml:153-155` —— `nanmuli-network: driver: bridge`
- **现象**：mihomo 安装脚本（`deploy/mihomo/install.sh`）部署在宿主机，绑定 `127.0.0.1:7890` 且 `allow-lan: false`。crawler 跑在 bridge 网络容器里，容器的 `127.0.0.1` 是容器自己，不是宿主机。若用户按 mihomo 文档把 `PROXY_URL` 设为 `http://127.0.0.1:7890`，crawler 实际连的是容器内 7890（无服务），代理失效；若设为 `http://host.docker.internal:7890` 又因 mihomo `allow-lan: false` + 绑定 127.0.0.1 被拒。
- **影响**：需要代理才能采集的境外信息源（日报系统核心依赖）在容器化部署下**无法走代理**，采集失败或走直连被墙，日报质量下降。这是 README 宣称"mihomo + crawler 协同"但实际跑不通的半成品。
- **根因/分析**：mihomo 设计为宿主机 systemd 服务（install.sh 装到 `/opt/mihomo`、`/etc/mihomo`），但 crawler 容器化后网络隔离。两套部署模式（裸机 crawler vs 容器 crawler）未统一代理可达性方案。已排除"crawler 用 host 网络"——compose 明确是 bridge。
- **修复方向**：
  1. mihomo `allow-lan: true` + `bind-address: "*"`，crawler `PROXY_URL` 指向宿主机 docker 网关（`http://host.docker.internal:7890` 或 `http://172.17.0.1:7890`），compose 加 `extra_hosts: ["host.docker.internal:host-gateway"]`（改动面：中，涉及 mihomo 安全暴露面，需配防火墙）
  2. 或把 mihomo 也容器化进 compose，crawler 用 `http://mihomo:7890`（改动面：大，需重构 mihomo 部署）
  3. 文档兜底：在 `deploy/mihomo/install.sh` 与 README 明确说明容器场景的 PROXY_URL 配法，避免误配 127.0.0.1。
- **关联**：次维度 [Arch]（部署模式割裂）；B11（代理管理主模块，引用此条）；横向主题"配置一致性"。

### [P3] [Bug] backend JVM 参数双源冲突   <!-- 编号：X01-04 -->
- **定位**：
  - `deploy/docker-compose.yml:58` —— `JAVA_TOOL_OPTIONS: ${BACKEND_JAVA_TOOL_OPTIONS:--XX:MaxRAMPercentage=70 -XX:+ExitOnOutOfMemoryError}`
  - `backend/Dockerfile:32` —— `ENV JAVA_OPTS="-Xms256m -Xmx512m -XX:MetaspaceSize=128m -XX:MaxMetaspaceSize=256m -XX:+UseG1GC -XX:MaxGCPauseMillis=200"`
  - `backend/Dockerfile:42` —— `ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]`
- **现象**：容器启动时 JVM 同时收到两套参数：①`JAVA_TOOL_OPTIONS`（compose 注入，JVM 自动拾取并打印"Picked up JAVA_TOOL_OPTIONS"）的 `-XX:MaxRAMPercentage=70`；②ENTRYPOINT 显式展开的 `$JAVA_OPTS` 的 `-Xms256m -Xmx512m`。当 `-Xmx` 显式指定时，`MaxRAMPercentage` 对堆的计算**被覆盖**，实际堆上限是 512m 而非 mem_limit 1024m 的 70%（约 716m）。
- **影响**：①堆被限制在 512m，backend 在高并发采集/日报回调时可能频繁 Full GC 或 OOM（`ExitOnOutOfMemoryError` 会直接杀进程，靠 restart: always 拉起，造成瞬时不可用）；②维护者看 compose 以为堆是 70% 可用（约 700m），实际只有 512m，容量规划失真；③`ExitOnOutOfMemoryError` + `restart: always` 组合下，OOM 会触发容器重启，但 depends_on 链上的 crawler 不会因 backend 重启而重启，可能出现 crawler 调用 backend 时连接被重置的窗口。
- **根因/分析**：Dockerfile ENV JAVA_OPTS 是为"裸机 2G 服务器"设计的历史参数（注释 line 31 明示），compose 化后引入 JAVA_TOOL_OPTIONS 但未删 Dockerfile 的 ENV，两者叠加。已排除"compose command 覆盖 ENTRYPOINT"——compose 未设 command，ENTRYPOINT 的 `$JAVA_OPTS` 必然展开。
- **修复方向**：
  1. Dockerfile 删除 `ENV JAVA_OPTS`，ENTRYPOINT 改为 `["java","-jar","app.jar"]` 让 `JAVA_TOOL_OPTIONS` 独占生效（改动面：小）
  2. 或 compose 删 JAVA_TOOL_OPTIONS，统一用 JAVA_OPTS（但失去按 env 灵活调整能力，不推荐）
  3. 推荐①，并确认 `MaxRAMPercentage=70` 在 mem_limit=1024m 下堆约 716m 足够。
- **关联**：次维度 [Arch]（配置双轨）。

### [P3] [Bug] crawler healthcheck 多行 heredoc 在 YAML 双引号下的转义存疑   <!-- 编号：X01-05 -->
- **定位**：`deploy/docker-compose.yml:131` —— `test: ["CMD-SHELL", "python - <<'PY'\nimport json, urllib.request\nresp = urllib.request.urlopen('http://localhost:8500/health', timeout=3)\nraise SystemExit(0 if json.load(resp).get('status') == 'healthy' else 1)\nPY"]`
- **现象**：healthcheck test 用 `CMD-SHELL`（走 `sh -c`），脚本体含字面 `\n` 转义和 `<<'PY'` heredoc。YAML 双引号字符串会把 `\n` 解析为真实换行符，传给 `sh -c` 的就是多行脚本，heredoc 合法。但这一行为依赖 Docker Compose 的 YAML 解析与 shell 实现，且可读性差。
- **影响**：[需查证] 实际运行中 healthcheck 是否真的返回 healthy。若 YAML 解析或 shell 版本把 `\n` 当字面字符，`sh -c "python - <<'PY'\nimport..."` 会被当成单行命令，heredoc 体无法正确读入，healthcheck 持续失败 → crawler 永远不 healthy → 若有下游依赖 crawler healthy 会阻断（当前无下游依赖 crawler healthy，但 backend 等待 crawler 回调的功能链路间接受影响）。即使当前无下游，crawler 不 healthy 在 `docker compose ps` 会显示 unhealthy，干扰监控判断。
- **根因/分析**：为了在 healthcheck 里校验 `status == 'healthy'`（而非仅 200），用了 heredoc 内嵌 python。YAML 双引号 `\n` → 换行 → sh heredoc 这条链路理论可行，但脆弱。已排除"python 不在 PATH"——crawler 镜像基于 playwright:python，python 必在 PATH。
- **修复方向**：
  1. 简化为 `test: ["CMD", "python", "-c", "import urllib.request,json; r=urllib.request.urlopen('http://localhost:8500/health',timeout=3); raise SystemExit(0 if json.load(r).get('status')=='healthy' else 1)"]`（单行 python -c，改动面：小）
  2. 或在镜像里写个 `healthcheck.sh`，compose `CMD-SHELL /app/healthcheck.sh`（改动面：中）
  3. 上线前务必 `docker inspect --format '{{.State.Health.Status}}' crawler-service` 实测确认 [需查证]。
- **关联**：无。

### [P3] [Bug] postgres 首次初始化可能超过 healthcheck 窗口，backend 等待超时   <!-- 编号：X01-06 -->
- **定位**：
  - `deploy/db/init-scripts/schema.sql` —— 1170 行，含 zhparser FTS 配置、GIN/ivfflat 索引、多表 + 种子数据
  - `deploy/docker-compose.yml:24-28` —— postgres healthcheck `interval: 5s timeout: 5s retries: 10`，无 `start_period`
  - `deploy/docker-compose.yml:81-85` —— backend `depends_on: postgres: condition: service_healthy`
- **现象**：postgres 官方镜像在首次启动（空卷）时会先 `initdb`，再执行 `/docker-entrypoint-initdb.d/schema.sql`（1170 行，含编译已完成的 zhparser 扩展创建 + GIN/ivfflat 索引构建 + 种子 admin 用户），**整个过程 pg_isready 可能先返回 success 但 schema 尚未跑完**（initdb 完成后、entrypoint 执行 sql 期间，postgres 已监听）。healthcheck 无 `start_period`，从启动即开始探测。
- **影响**：①postgres 在 schema.sql 执行期间即报 healthy，backend 依赖满足开始启动，但此时表/扩展可能还没建完，backend 首次连接报"relation does not exist"或"extension zhparser not found"，启动失败（靠 restart: always 重试，可能多次拉起才成功）；②ivfflat 索引构建在数据量大时耗时长，放大窗口。MVP 数据量小风险低，但全新部署首次启动是高发场景。
- **根因/分析**：`pg_isready` 只校验连接接受，不校验 schema 就绪，这是 postgres 镜像的已知特性。本项目 schema.sql 重（1170 行 + FTS + 向量索引），窗口更明显。已排除"backend 用 Flyway 兜底"——Flyway 未集成（见 §9 已知线索）。
- **修复方向**：
  1. postgres healthcheck 加 `start_period: 60s`（改动面：小），并在 `test` 里追加 schema 就绪校验如 `pg_isready ... && psql -c "select 1 from pg_extension where extname='zhparser'"`（改动面：中）
  2. 或 backend 容器启动加重试退避（Spring Boot 已有连接重试，但表缺失不是连接问题）
  3. 推荐①的 start_period，最小且对症。
- **关联**：B15（schema 主模块）、X02（schema 跨库）。

---

## `[Security]` 安全漏洞

> 排查范围：端口暴露、网络隔离、secrets 注入、镜像基线、nginx 安全头、postgres/redis 公网。技术栈特定重点（SSRF/Cookie/CSRF/AES）归各自主模块，本节只记部署层视角。

### [P1] [Security] 内部服务端口全部对宿主机公网发布   <!-- 编号：X01-07 -->
- **定位**：`deploy/docker-compose.yml:20-21`（postgres `"5433:5432"`）、`:39-40`（redis `"6380:6379"`）、`:77-78`（backend `"8081:8081"`）、`:123-124`（crawler `"8500:8500"`）
- **现象**：四个内部服务端口全部 `ports:` 映射到宿主机。只有 frontend 是 `"80:80"` 对外，其余本应只在 `nanmuli-network` 内部通信。
- **影响**：
  - **postgres 5433**：含 admin 用户、全文博客数据、sys_config（含 AES 密文配置）、采集任务，公网可连 + 默认弱口令风险（X02/B06 已记种子 admin123，DB_PASSWORD 由用户设但若弱则暴露）。
  - **redis 6380**：无密码（compose command 未设 `requirepass`），Sa-Token token（db1）、业务缓存（db0）公网可读，可伪造 token 绕过登录。
  - **backend 8081**：绕过 nginx，直接访问 `/actuator/health`（信息泄露有限）及所有 `/api/**`，绕过 nginx 限流（本就无效，见 X01-02）与未来安全头；`/api/internal/collector/callback` 本应只 crawler 调用，公网可达（靠 X-Callback-Key 鉴权，见 B09）。
  - **crawler 8500**：`/docs`（FastAPI Swagger）公网暴露接口结构，`/health` 泄露，采集接口靠 X-API-Key 鉴权但攻击面增大。
- **根因/分析**：`ports:` 映射疑似为开发调试（本地连库、看 docs）保留，但生产部署未移除。Docker `ports` 默认绑定 `0.0.0.0`。README 的端口表（deploy/README.md:58-64）把 5433/6380/8081/8500 列为"宿主机端口"，固化了这个错误心智。已排除"宿主机防火墙兜底"——compose 不依赖也无法假设宿主机防火墙。
- **修复方向**：
  1. 生产 compose 用 `expose:`（仅容器间）替换内部服务的 `ports:`，只保留 frontend 的 `80:80`（改动面：小，但破坏本地调试，建议用 `compose.override.yml` 区分 dev/prod）
  2. 或 `ports: - "127.0.0.1:5433:5432"` 限定本地回环（改动面：小，推荐）
  3. redis 必须加密码（`--requirepass` + backend REDIS_PASSWORD，当前 application-prod.yml:17 有 `password: ${REDIS_PASSWORD:}` 占位但 compose 未注入且 redis 未开 requirepass）。
- **关联**：B06（Sa-Token/Redis token）、B09（callback 鉴权）、B10（CrawlerTaskClient）；次维度 [Bug]。

### [P2] [Security] redis 无密码 + Sa-Token alone-redis 公网可伪造 token   <!-- 编号：X01-08 -->
- **定位**：
  - `deploy/docker-compose.yml:36` —— `command: redis-server --maxmemory 100mb --maxmemory-policy allkeys-lru`（**无 requirepass**）
  - `backend/src/main/resources/application-prod.yml:17` —— `password: ${REDIS_PASSWORD:}`（默认空）
  - `application-prod.yml:33-37` —— Sa-Token `alone-redis: database: 1`（token 存 db1）
- **现象**：redis 容器未设密码，compose 也未注入 `REDIS_PASSWORD`。结合 X01-07 的 6380 公网发布，任何人可连 redis 6380，`SELECT 1` 后 `KEYS *` 拿到 Sa-Token 会话，或直接 `SET` 伪造 admin token。
- **影响**：鉴权被完全绕过，可冒充管理员对博客/采集/日报/配置全权限操作。即便不公网（修了 X01-07），同网段其他容器或宿主机本地用户也能未授权访问。
- **根因/分析**：redis 镜像默认无密码，compose command 只配了内存策略。application-prod.yml 有 `password` 占位但链路未打通（compose env 无 REDIS_PASSWORD，redis 也未 requirepass）。
- **修复方向**：
  1. compose command 加 `--requirepass ${REDIS_PASSWORD:?...}`，compose backend/redis env 注入 `REDIS_PASSWORD`，.env.example 补该项（改动面：中，需同步 backend/Sa-Token/CrawlerTaskClient 等 redis 消费方）
  2. 即便内网也应设密码（深度防御）。
- **关联**：B06（Sa-Token 主模块）、X01-07；次维度 [Bug]。

### [P2] [Security] postgres 自建镜像基线用 `ankane/pgvector:latest` 未固定 tag   <!-- 编号：X01-09 -->
- **定位**：`deploy/db/Dockerfile:10` —— `FROM ankane/pgvector:latest`
- **现象**：基础镜像用 `:latest`，每次构建可能拉到不同版本（pgvector 仓库已 archived，上游迁移到 `pgvector/pgvector`，[需查证] ankane/pgvector:latest 当前是否仍可用/更新）。SCWS 1.2.3 / zhparser 2.2 的 ARG 固定了，但基础镜像漂移。
- **影响**：①构建不可复现，不同时间构建的镜像 PG 主版本可能不同（PG 16 vs 17），数据目录格式不兼容，升级时数据卷无法启动；②ankane/pgvector 仓库已归档（训练知识，[需查证]），未来 `:latest` 可能消失，构建直接失败；③与 CLAUDE.md "PostgreSQL 15+" 声明不一致——`:latest` 当前可能是 PG 17。
- **根因/分析**：`ankane/pgvector` 是早期社区镜像，官方已迁移到 `pgvector/pgvector`（[需查证] 当前 tag）。用 `:latest` 是图省事，未考虑可复现与上游归档风险。
- **修复方向**：
  1. 固定为具体 tag，如 `ankane/pgvector:pg16` 或迁移到 `pgvector/pgvector:pg16`，并在 README 记录 PG 大版本（改动面：小，但需验证 zhparser 在新基础镜像的编译兼容性）
  2. 同步更新 CLAUDE.md "PostgreSQL 15+" 的口径。
- **关联**：次维度 [Deps]；B15（schema 主模块）。

### [P3] [Security] nginx 反代未对 backend 做路径白名单，/api/internal/* 公网可达   <!-- 编号：X01-10 -->
- **定位**：
  - `deploy/nginx.conf:37-45` —— `location /api/ { proxy_pass http://backend:8081; }`（全路径透传）
  - backend `InternalCallbackController` 暴露 `/api/internal/collector/callback`（见 B09）
- **现象**：nginx 对 `/api/` 全段反代，没有在网关层屏蔽 `/api/internal/**`、`/api/admin/**` 的外部访问。内部回调端点、管理端点都对外可达，鉴权完全压在 Sa-Token + 双向 key 上。
- **影响**：纵深防御缺失。一旦 B06 的 URL 前缀鉴权或 B09 的回调 key 出现漏洞，nginx 不做任何拦截。crawler 直接走容器内 `backend:8081` 是合法的，但经 nginx 的 `/api/internal/*` 公网访问应被拒。
- **根因/分析**：nginx 配置追求通用反代，未做路径分级。属设计取舍，但 MVP 试用场景下增加风险。
- **修复方向**：
  1. nginx 加 `location ^~ /api/internal/ { return 403; }`（仅允许容器内 crawler 直连 backend:8081，不走 nginx）（改动面：小）
  2. 或限制 `/api/internal/` 只接受来自 crawler 容器 IP 段（nginx `allow/deny`，改动面：中）
  3. 需与 B09 的 callback 鉴权方案统筹，避免双重维护。
- **关联**：B06（鉴权）、B09（callback 主模块）。

---

## `[Arch]` 架构与技术债

> 排查范围：compose 编排结构、配置漂移、deploy.sh 与 compose 一致性、镜像构建缓存、文档与实现一致。共享对象按 §8.6 只引用。

### [P2] [Arch] deploy.sh 用 v1 docker-compose 且与 compose 编排脱节   <!-- 编号：X01-11 -->
- **定位**：
  - `deploy/deploy.sh:21` —— `command -v docker-compose`（v1 命令）
  - `deploy/deploy.sh:41-42` —— `docker-compose -f docker-compose.yml pull` / `up -d --build`（**未传 `--env-file .env`**）
  - `deploy/README.md:53` —— 推荐命令是 `docker compose --env-file .env up -d --build`（v2 + env-file）
- **现象**：deploy.sh ①用已废弃的 v1 `docker-compose`（带连字符），新版 Docker Desktop 默认只装 v2 `docker compose`（空格）；②启动时不传 `--env-file .env`，而 compose.yml 里大量 `${DB_PASSWORD:?set ...}` 强制要求 env，若无 `.env` 在同目录且 compose 默认不读（compose v2 默认读 `.env`，但 v1 行为不同），可能因 `:?` 直接报错启动失败；③deploy.sh 选项 2"仅部署爬虫"用 `docker run` 单独跑 crawler（`-e MAX_PAGES_DEFAULT=10` 等参数与 compose 完全不同），与正式编排脱节；④选项 5 mihomo 管理调用 `install.sh`，但未处理 X01-03 的容器可达性问题。
- **影响**：①用户照 deploy.sh 部署可能因 v1/v2 差异、env 缺失直接失败，转而手动敲 README 的命令，deploy.sh 形同虚设；②"仅部署爬虫"选项参数过时（MAX_PAGES_DEFAULT 不是 crawler 现有配置项，[需查证]），误导；③deploy.sh 与 README 推荐命令口径不一，维护者困惑。
- **根因/分析**：deploy.sh 是早期脚本，compose.yml 与 README 后续演进（加 `:?` 强制、改 v2、加 env-file）未回填 deploy.sh。
- **修复方向**：
  1. deploy.sh 改用 `docker compose`（v2），所有命令补 `--env-file .env`（改动面：小）
  2. 删除选项 2"仅部署爬虫"或与 compose 的 crawler 服务对齐（改动面：中）
  3. 或直接弃用 deploy.sh，README 已有完整命令，脚本冗余（改动面：小，删文件 + 更新 README）
- **关联**：X04（发布脚本主模块，引用此条）。

### [P3] [Arch] healthcheck 在 Dockerfile 与 compose 双重声明且参数不一   <!-- 编号：X01-12 -->
- **定位**：
  - `backend/Dockerfile:38-39` —— `HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3`
  - `deploy/docker-compose.yml:86-91` —— backend healthcheck `interval:10s timeout:5s retries:12 start_period:60s`
  - `crawler-service/Dockerfile:28-29` —— `HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3`
  - `deploy/docker-compose.yml:130-135` —— crawler healthcheck `interval:10s timeout:5s retries:12 start_period:30s`
- **现象**：backend 与 crawler 都在 Dockerfile 和 compose 里各写了一份 HEALTHCHECK，参数不同（Dockerfile 30s/10s/3 次，compose 10s/5s/12 次；crawler start_period Dockerfile 60s vs compose 30s）。compose 的 healthcheck 会**覆盖** Dockerfile 的（compose 优先级高），Dockerfile 那份是死配置。
- **影响**：①维护者改 Dockerfile HEALTHCHECK 不生效，困惑；②两份参数口径不一，实际生效的以 compose 为准，但 Dockerfile 的注释（如 crawler start-period 60s）误导；③frontend/redis/postgres 只在单处声明（frontend 甚至完全没有），风格不统一。
- **根因/分析**：Dockerfile 先写，compose 化时又加，未删 Dockerfile 那份。
- **修复方向**：
  1. 统一：只在 compose 声明 healthcheck（编排层统一管理），Dockerfile 删除 HEALTHCHECK（改动面：小）
  2. 或反过来只在 Dockerfile（但失去 compose 按 env 调参能力，不推荐）
  3. 推荐①，并把 frontend 补上 healthcheck（nginx 健康检查 `wget --spider http://localhost/`）。
- **关联**：X01-05（crawler healthcheck 转义）。

### [P3] [Arch] .env.example 缺 CRAWLER_SERVICE_URL/JAVA_API_URL 等运行时变量，但 README 列为必填   <!-- 编号：X01-13 -->
- **定位**：
  - `deploy/.env.example:1-49` —— 含 DB_PASSWORD/BLOG_SECURITY_ENCRYPTION_KEY/CRAWLER_API_KEY/CRAWLER_CALLBACK_API_KEY/AI_*/资源限额/PROXY_URL/JAVA_API_URL/CALLBACK_URL/CRAWLER_CALLBACK_URL/STORAGE_TYPE/CORS
  - `deploy/README.md:68-83` 必填表列了 `CRAWLER_SERVICE_URL`（compose 内联默认 `http://crawler:8500`，.env.example 无）
  - `deploy/docker-compose.yml:67` —— `CRAWLER_SERVICE_URL: http://crawler:8500`（compose 硬编码，非 env 注入）
- **现象**：compose 中部分变量（CRAWLER_SERVICE_URL、CRAWLER_CALLBACK_URL、JAVA_API_URL、CALLBACK_URL）直接硬编码默认值或用 `${VAR:-default}`，未全部进 .env.example。README 必填表把 CRAWLER_SERVICE_URL 列为必填，但实际 compose 写死了，用户在 .env 改不生效（compose 未引用 `${CRAWLER_SERVICE_URL}`）。
- **影响**：①用户按 README 在 .env 设 CRAWLER_SERVICE_URL 无效，compose 用硬编码值，非标准部署（如 crawler 换端口/主机）无法通过 env 调整；②.env.example 与 README 口径不一，配置项半数走 env 半数走硬编码，心智负担。
- **根因/分析**：compose 演进中，容器间 URL 通常固定（走 docker DNS），开发者图省直接硬编码，未把"用户可调"和"容器内固定"区分开。
- **修复方向**：
  1. 明确分类：容器间互联 URL（CRAWLER_SERVICE_URL/JAVA_API_URL/CALLBACK_URL/CRAWLER_CALLBACK_URL）固定写死在 compose 并加注释"请勿在 .env 修改"，README 必填表移除；用户可调项（端口、密码、AI、资源）才进 .env.example（改动面：小，文档 + 注释）
  2. 或全部提为 `${VAR:-default}`，.env.example 全列（改动面：中，增加灵活性但易误配）
  3. 推荐①，MVP 场景容器间 URL 不应让用户调。
- **关联**：X06（配置一致性主模块，引用此条）。

### [P4] [Arch] 单 bridge 网络，无服务间网络隔离   <!-- 编号：X01-14 -->
- **定位**：`deploy/docker-compose.yml:153-155` —— 所有 5 服务共用 `nanmuli-network: driver: bridge`
- **现象**：frontend/backend/crawler/postgres/redis 全在一个 bridge，任意容器可访问任意其他容器的任意端口。
- **影响**：理想分层应是 frontend 只能到 backend，backend 到 postgres/redis/crawler，crawler 到 backend/postgres（若需要），postgres/redis 不应被 frontend/crawler 直连。当前 frontend 理论上可直连 postgres:5432、redis:6379（虽然应用代码不会这么做），攻击面大于必要。
- **根因/分析**：单网络是 MVP 简化，多网络（frontend_net/backend_net/data_net）增加编排复杂度，单人维护过度设计。
- **修复方向**：MVP 阶段维持单网络可接受（标 P4）。若硬化，拆 `frontend_net`（frontend/backend）+ `data_net`（backend/postgres/redis）+ `crawler_net`（crawler/backend），frontend 进不了 data_net。改动面：中。无需立即调整。
- **关联**：X01-07（端口发布）。

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| ankane/pgvector | `:latest`（未固定） | `deploy/db/Dockerfile:10` | 上游已归档，迁移到 `pgvector/pgvector`，tag 漂移 | X01-09 |
| SCWS | 1.2.3（ARG 固定） | `deploy/db/Dockerfile:14` | 较旧，但 zhparser 2.2 依赖 | 编译安装 |
| zhparser | 2.2（ARG 固定） | `deploy/db/Dockerfile:15` | 较旧，[需查证] 是否有新版 | 中文 FTS |
| redis | `7-alpine` | `deploy/docker-compose.yml:31` | 7.x 主线，建议固定到 `7.x-alpine` 具体 tag | 未固定小版本 |
| nginx | `1.27-alpine` | `frontend/Dockerfile:13` | 1.27 主线，建议固定小版本 | |
| node | `20-alpine` | `frontend/Dockerfile:3` | Node 20 LTS，可升至 22 LTS | 构建阶段 |
| maven | `3.9-eclipse-temurin-21-alpine` | `backend/Dockerfile:5` | 当前稳定 | 构建阶段 |
| eclipse-temurin | `21-jre-alpine` | `backend/Dockerfile:18` | JDK 21 LTS，运行镜像 | |
| playwright python | `v1.59.0-jammy` | `crawler-service/Dockerfile:5` | 固定版本，但 jammy（Ubuntu 22.04）较新 | [需查证] crawl4ai 0.8.6 与 playwright 1.59 兼容 |
| crawl4ai | `~=0.8.6` | `crawler-service/requirements.txt` | 主模块 C 系列 | |
| Docker Compose | v2（README）/ v1（deploy.sh） | 文档/脚本 | deploy.sh 仍用 v1 命令 | X01-11 |

> 排查范围：各 Dockerfile FROM、compose image、requirements.txt 顶部。未命中额外 CVE 级风险（具体 CVE 归各主模块 Deps 节）。

### [P3] [Deps] redis/nginx 基础镜像未固定小版本 tag   <!-- 编号：X01-15 -->
- **定位**：`deploy/docker-compose.yml:31`（`redis:7-alpine`）、`frontend/Dockerfile:13`（`nginx:1.27-alpine`）
- **现象**：redis 只锁大版本 7，nginx 只锁 1.27，小版本/补丁漂移。
- **影响**：构建不可完全复现，安全补丁随小版本进来是好事，但也可能引入行为变化（如 nginx 1.27.x 某次小版本的 default_type 调整）。
- **根因/分析**：`-alpine` tag 会跟随上游最新小版本，是常见的"锁大放小"折中。
- **修复方向**：MVP 可接受（P3）。生产建议固定到具体 digest 或 `7.4-alpine`、`1.27.3-alpine`。改动面：小。
- **关联**：无。

### [P3] [Deps] crawler 镜像体积大（playwright + chromium），构建慢且无层缓存优化   <!-- 编号：X01-16 -->
- **定位**：`crawler-service/Dockerfile:5-19`
- **现象**：基础镜像是 `mcr.microsoft.com/playwright/python:v1.59.0-jammy`（预装 Chromium，镜像 2GB+）。`COPY requirements.txt` 后 `pip install`，再分多次 `COPY` 各目录。requirements.txt 变动会重跑 pip，但应用代码分目录 COPY 已做了基本的层缓存。
- **影响**：①镜像大，拉取/推送慢，磁盘占用高（5 服务总镜像可能 >5GB）；②`pip install` 在 playwright 镜像里装 crawl4ai/fastapi/httpx 等，构建时间数分钟；③无 multi-stage，运行镜像含构建期残留（虽 playwright 本就大，影响有限）。
- **根因/分析**：crawl4ai 依赖 playwright，playwright 依赖 chromium，无可避免。当前已是官方 playwright 镜像，合理。
- **修复方向**：
  1. requirements.txt 拆 `requirements-base.txt`（少变的 fastapi/httpx）+ `requirements-app.txt`（业务代码依赖），优化缓存命中（改动面：中）
  2. 或接受现状，playwright 镜像已是较优解（改动面：无）
  3. MVP 阶段推荐接受现状（P3 记录）。
- **关联**：无。

---

## `[Design]` 功能设计合理性

> 必填。从真实使用（单人维护的技术博客 + 每工作日 AI 日报 + MVP 试用）出发，回答 §2.5 中相关问题。

**审视结论**：

1. **可运维性**：部署链路的可观测性偏弱。`restart: always` 是唯一的故障自愈，OOM/崩溃靠无限重启，无告警、无死信通知。健康检查存在但 frontend 缺失、crawler 转义存疑（X01-05）、postgres schema 未就绪即报 healthy（X01-06），`docker compose ps` 显示的状态可信度有限。日志路径错配（X01-01）让卷内日志为空，排障只能靠 `docker logs` 实时流，无法历史追溯。对于"每工作日自动日报"的场景，crawler/backend 在夜间无人值守跑，一次静默失败可能到第二天才发现，缺少"任务失败主动通知"的运维闭环。

2. **单点与扩展**：整套部署是单机单实例，postgres/redis/backend/crawler/frontend 各一份，无水平扩展能力。MVP 试用（单人 + 少量内部服务）完全够用，但 README 声称"允许最多两个内部服务调用 crawler"，一旦 crawler 单实例 OOM（1536m 跑 playwright + AI），所有调用方阻塞。设计上未留"crawler 故障时 backend 降级直连采集"的退路（B10 CrawlerTaskClient 的超时/降级行为归 B10）。单机假设也意味着宿主机宕机=全站宕机，无 HA，对 MVP 可接受，但应在 README 明确"非生产级 HA"。

3. **secrets 管理**：secrets 走 `.env` 文件 + compose `${VAR:?}` 强制存在性校验，check-deploy-env.ps1 校验非空与 BLOG_SECURITY_ENCRYPTION_KEY 长度≥16，是 MVP 阶段合理的轻量方案。但①无 secrets 轮换流程；②`.env` 在宿主机明文（虽有 .gitignore），无加密落盘；③DB_PASSWORD/CRAWLER_API_KEY 无强度校验（check-deploy-env 只查存在性）；④redis 无密码（X01-08）让 secrets 体系有短板。对试用版可接受，需在 README 标注"轮换与强度由用户负责"。

### [P2] [Design] 缺少部署级的失败可观测与告警闭环   <!-- 编号：X01-17 -->
- **定位**：`deploy/docker-compose.yml`（全局，5 服务均仅 `restart: always`，无日志聚合/告警/死信）
- **现象**：部署层只有 restart 策略，无任何主动通知机制。任务失败（采集失败、日报生成失败、OOM 重启）不会被推送给维护者。
- **影响**：夜间自动日报失败静默，第二天用户访问看到的是昨日旧日报或空，体验断层且难以第一时间定位。
- **建议方向**：①接入轻量日志收集（如 loki/dozzle）或至少配置 `docker compose logs` 轮转；②backend/crawler 任务失败时调用 webhook（飞书/邮件），由应用层实现而非部署层。改动面：中。标 P2 建议。
- **关联**：C04（日报编排失败处理）、C10（调度器告警）。

### [P4] [Design] 部署文档与实际编排的口径需统一   <!-- 编号：X01-18 -->
- **定位**：`deploy/README.md:8-16`（部署结论）、`:58-64`（端口表）、`:24-26`（nginx 目录说明）
- **现象**：README 声称"`docker compose config` 通过""前端 Docker 构建使用 npm ci"，但未提及 X01-01 的路径错配、X01-02 的限流失效、X01-07 的端口公网发布等实际风险，呈现"部署链路已就绪"的乐观口径。端口表把 5433/6380/8081/8500 全列为"宿主机端口"固化错误心智。nginx 目录把 `conf.d/default.conf` 标"可选"掩盖死代码。
- **影响**：维护者按 README 心智运维，误以为限流在跑、上传在卷里、内部端口安全，直到事故才发现。
- **建议方向**：在修复 X01-01/02/07 后，同步更新 README，明确已知限制与正确配置。改动面：小。标 P4。
- **关联**：X05（文档一致性主模块）。

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | X01-01, X01-07 |
| P2 | 6 | X01-02, X01-03, X01-08, X01-09, X01-11, X01-17 |
| P3 | 7 | X01-04, X01-05, X01-06, X01-10, X01-12, X01-13, X01-15, X01-16 |
| P4 | 2 | X01-14, X01-18 |

> 注：X01-05、X01-06 含 `[需查证]` 成分，定级按"若属实"的影响估，待实测复核。

### Top 风险（本模块最该先看的 3 条）

1. **X01-01 prod 上传/日志路径与卷挂载不一致** —— 直接导致上传文件丢失、日志不进卷，MVP 试用最基础的上传功能在容器化部署下数据不持久，且 README 承诺与实现不符。
2. **X01-07 内部服务端口全部公网发布 + X01-08 redis 无密码** —— postgres/redis/backend/crawler 端口对宿主机 0.0.0.0 暴露，redis 无密码可伪造 Sa-Token 绕过鉴权，是部署层最大安全短板。
3. **X01-02 nginx 限流主配置是死代码** —— 维护者以为有限流实际没有，登录/API 无网关层防护，叠加 B06 的 URL 前缀鉴权薄弱，纵深防御缺失。

### 修复优先级建议

- **立即（P1）**：
  - X01-01：统一 upload-path/logback 路径到 `/app/uploads`、`/app/logs`（或改 Dockerfile/compose 挂载点），迁移已有数据
  - X01-07：内部服务端口改 `127.0.0.1:port:port` 或 `expose:`，仅 frontend 对外
  - X01-08：redis 加 requirepass（与 X01-07 可合并修复）
- **计划（P2）**：
  - X01-02：清理 nginx 死代码 + 补 client_max_body_size + 决定是否启用限流
  - X01-03：mihomo 与 crawler 容器网络可达性方案（allow-lan + extra_hosts 或容器化 mihomo）
  - X01-09：固定 pgvector 基础镜像 tag
  - X01-11：deploy.sh 迁移到 docker compose v2 + env-file，或弃用
  - X01-17：补失败告警 webhook（应用层为主）
- **择机（P3/P4）**：
  - X01-04/05/06/10/12/13/15/16：参数对齐、healthcheck 修正、文档统一
  - X01-14/18：网络隔离、文档口径

### 排查盲区 / 待复核

- **X01-05**：crawler healthcheck 多行 heredoc 在 YAML 双引号下的实际解析行为，需 `docker inspect` 实测确认 healthcheck 是否真返回 healthy。[需查证]
- **X01-06**：postgres 首次启动执行 1170 行 schema.sql 的实际耗时，需在干净卷上实测，确认是否真的早于 backend 启动就绪。[需查证]
- **X01-09**：`ankane/pgvector` 仓库当前状态（是否归档/`:latest` 是否仍可拉取），需 `docker pull` 实测或查上游仓库。[需查证]
- **X01-16**：crawl4ai 0.8.6 与 playwright v1.59.0-jammy 镜像的兼容性，需在容器内 `pip check` 或跑 crawler smoke。[需查证]
- **未覆盖**：本次未实测 `docker compose config` 展开（命令边界禁），仅静态读 yml；未跑镜像构建验证 Dockerfile 正确性；mihomo install.sh 完整内容仅读 head 40 行，其代理订阅 `{{SUBSCRIPTION_URL}}` 模板渲染逻辑未深查。
