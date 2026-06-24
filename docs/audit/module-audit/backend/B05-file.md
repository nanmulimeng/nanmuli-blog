# B05 文件 File 排查报告

> **模块编号**：B05
> **排查范围**：文件上传、md5 去重、缩略图、路径遍历防护、storage_type、usage_type 多态软引用、列表/删除
> **基线 commit**：`6ae930098405f4d0553d96a852f3345d0f39682e`
> **工作区状态**：脏（未提交改动涉及 `ConfigRepositoryImpl.java`、`WebCollectPageMapper.java`、`crawler-service/*`、`deploy/README.md`、`docs/audit/full-project-risk-register.md`、`scripts/release/release-gate.ps1`，以及新增 `backend/src/test/.../webcollector/`。**本模块文件均无未提交改动**）
> **排查日期**：2026-06-23
> **排查人**：B05 模块排查 agent
> **状态**：待复核

---

## 模块概览

**职责**：管理博客后台上传文件（图片/文档/压缩包）的存储、md5 去重、缩略图生成与列表/删除。

**关键文件**：
- `backend/src/main/java/com/nanmuli/blog/interfaces/rest/FileController.java` —— REST 入口（`/api/admin/file/upload|list|{id}|regenerate-thumbnails` + 公开 `/api/file/{id}`）
- `backend/src/main/java/com/nanmuli/blog/application/file/FileAppService.java` —— 上传/校验/去重/删除/缩略图后补编排（核心 292 行）
- `backend/src/main/java/com/nanmuli/blog/application/file/ImageThumbnailService.java` —— 基于 JDK `ImageIO` + `Graphics2D` 的 400px 缩略图生成
- `backend/src/main/java/com/nanmuli/blog/domain/file/BlogFile.java` —— 实体（`sys_file`）
- `backend/src/main/java/com/nanmuli/blog/infrastructure/persistence/file/FileRepositoryImpl.java` —— MP 仓储实现
- `backend/src/main/java/com/nanmuli/blog/infrastructure/config/web/WebMvcConfig.java:51-56` —— 静态资源映射 `/uploads/**` → 本地 `upload-path`
- `deploy/nginx/conf.d/default.conf:47-54` —— `/uploads/` 反代到 backend
- `deploy/db/init-scripts/schema.sql:372-413`、`backend/src/main/resources/db/init.sql:353-395` —— `sys_file` 定义（两轨一致）

**对外接口 / 依赖**：
- 对外：`POST/GET/DELETE /api/admin/file/*`（admin 鉴权）、`GET /api/file/{id}`（公开）、静态资源 `/uploads/**`
- 依赖：Sa-Token（admin 拦截）、MyBatis Plus（逻辑删除 + 分页）、JDK `javax.imageio.ImageIO` / `java.awt`（缩略图）、Spring multipart、配置 key `blog.file.*`、表 `sys_file`
- **下游消费方**：无（见 B05-09，ArticleAppService 不引用 BlogFile/cover/fileId）

**已读文件清单**：
- `backend/.../interfaces/rest/FileController.java` —— 通读
- `backend/.../application/file/FileAppService.java` —— 通读
- `backend/.../application/file/ImageThumbnailService.java` —— 通读
- `backend/.../domain/file/BlogFile.java` —— 通读
- `backend/.../domain/file/FileRepository.java` —— 通读
- `backend/.../infrastructure/persistence/file/FileRepositoryImpl.java` —— 通读
- `backend/.../infrastructure/persistence/file/BlogFileMapper.java` —— 通读（仅 `extends BaseMapper`）
- `backend/.../application/file/{command/UploadFileCommand,dto/FileDTO,query/FilePageQuery}.java` —— 通读
- `backend/.../infrastructure/config/web/WebMvcConfig.java` —— 通读
- `backend/.../infrastructure/config/security/SaTokenConfig.java` —— 通读
- `backend/src/main/resources/{application.yml,application-prod.yml}` —— 通读 multipart/blog.file 段
- `backend/src/main/resources/db/init.sql:350-395` —— 片段（sys_file 定义）
- `deploy/db/init-scripts/schema.sql:370-413` —— 片段
- `deploy/nginx/conf.d/default.conf` —— 通读
- `backend/src/test/java/.../file/FileAppServiceTest.java` —— 通读
- `frontend/src/api/file.ts`、`frontend/src/views/admin/file/Index.vue:1-60` —— 片段
- grep：`setUsageType|setRefId|setUserId` 在 `BlogFile` 上的调用、`fileId/cover` 在 ArticleAppService 的引用、md5 UNIQUE 约束、`@TableLogic` 全局配置

**主模块归属**：本模块是文件上传/存储链路的**主模块**，深查路径遍历/MIME/md5/缩略图/storage_type/usage_type/删除/绝对路径泄漏。对共享对象（Sa-Token 拦截、`@TableLogic` 逻辑删除、schema 双轨、CORS）按 §8.6 只引用：Sa-Token 配置 → B06、schema 漂移 → B15、CORS → B16。

---

## `[Bug]` 代码正确性与潜在缺陷

> 排查范围：FileAppService（upload/delete/list/regenerateMissingThumbnails）、ImageThumbnailService、FileRepositoryImpl、BlogFile 字段使用、md5 去重与逻辑删除组合。

### [P2] [Bug] md5 去重缺 DB 层唯一约束，并发上传可双写 <!-- 编号：B05-01 -->
- **定位**：`deploy/db/init-scripts/schema.sql:410`、`backend/src/main/resources/db/init.sql:392`（`idx_file_md5` 为普通 INDEX，非 UNIQUE）；写入逻辑 `FileAppService.java:127-167`（先 `findByMd5` 再 `insert`，无锁）
- **现象**：md5 仅建普通索引。`upload()` 流程是"查 md5 → 不存在则写盘 → insert"，应用层 check-then-act 非原子。两个请求同时上传同 md5 文件时，两个事务都查不到，都会写盘并 insert，落库两行相同 md5（不同 fileName、不同 id）。
- **影响**：单人维护场景并发概率低，但前端 md5 编辑器同图重复粘贴、管理端双击上传、浏览器自动重试时可能触发，造成存储冗余 + 后续 `findByMd5` 抛 `TooManyResultsException`（MP `selectOne` 在多行时直接异常，见 B05-02）。
- **根因/分析**：去重纯靠应用层查询，DB 层无 UNIQUE 兜底。已排除误判：逻辑删除全局开启（`application.yml:48-51`），即便加 UNIQUE 也需配合 `md5 + is_deleted` 复合约束，否则软删后无法重传。
- **修复方向**：①`sys_file` 加 `UNIQUE(md5) WHERE is_deleted = false` 部分唯一索引（PG 支持）；②upload 写盘前加基于 md5 的分布式锁或 DB 唯一约束 + 捕获 `DuplicateKeyException` 回查。（改动面：中，涉及 schema 迁移 + B15 协同）

### [P2] [Bug] findByMd5 在历史重复 md5 数据上抛 TooManyResultsException 致上传中断 <!-- 编号：B05-02 -->
- **定位**：`FileRepositoryImpl.java:37-41`（`selectOne`）；触发条件 `FileAppService.java:129`
- **现象**：MP `selectOne(wrapper)` 当结果 >1 行时抛 `TooManyResultsException`。若历史数据因 B05-01 已存在重复 md5 行，任何后续上传（即使是新文件，先走 `findByMd5` 这步）都会在去重查询阶段直接异常，整个 upload 不可用。
- **影响**：去重查询失败 → 上传链路整体 500。一旦 B05-01 触发过一次重复，去重机制反而变成单点故障，需人工清库才能恢复。
- **根因/分析**：`selectOne` 无 multi-result 防护。已排除：当前生产数据若从未并发上传则不会触发，属潜伏风险。
- **修复方向**：①配合 B05-01 加唯一约束根除重复；②`findByMd5` 改用 `selectList(...).stream().findFirst()` 或 `last("LIMIT 1")`，容忍历史脏数据。（改动面：小）

### [P2] [Bug] 删除接口不校验文件归属，任意已登录 admin 可删任意文件 <!-- 编号：B05-03 -->
- **定位**：`FileController.java:45-49`、`FileAppService.java:251-257`
- **现象**：`delete(id)` 只 `findById` 后直接 `deleteById`，不读取也不校验 `userId`。`BlogFile.userId` 字段存在但 **upload 时从未赋值**（见 B05-09），实际所有行 `userId` 均为 NULL。
- **影响**：当前单管理员场景下无实际越权面；但 `userId` 一旦被启用（B05-09 修复方向），多管理员/多用户接入时此处缺校验会成为水平越权点。公开接口 `/api/file/{id}` 无删除能力，影响仅限 admin 内部。
- **根因/分析**：删除未做归属断言，且 `userId` 字段长期空置使任何"补归属校验"的修复都形同虚设（NULL 比较恒 false 或恒 true，取决于写法）。
- **修复方向**：①upload 时 `blogFile.setUserId(StpUtil.getLoginIdAsLong())`；②delete 时校验 `file.getUserId().equals(currentUserId)` 或显式 admin 角色判断。（改动面：中，关联 B05-09）

### [P3] [Bug] 缩略图高度计算未防 origW==0，理论触发除零 <!-- 编号：B05-04 -->
- **定位**：`ImageThumbnailService.java:51`（`int thumbH = (int) Math.round((double) origH / origW * THUMB_WIDTH);`）
- **现象**：若 `ImageIO.read` 返回 `width=0` 的退化 BufferedImage（某些畸形/截断图片可能产生），下一步 `origW <= THUMB_WIDTH` 会短路走"只记录尺寸"分支返回（line 52-55），实际上不会执行到除法。但分支顺序依赖 `origW <= THUMB_WIDTH`（400）先成立——若构造出 `width=0` 的图，`0 <= 400` 成立，安全返回。
- **影响**：经分支分析实际不会触发除零（被 line 52 短路保护）。但代码可读性上，除法在短路判定**之后**才显式出现，维护者改顺序时易引入 bug。无运行时风险。
- **根因/分析**：已确认 line 52 的 `origW <= THUMB_WIDTH` 短路覆盖了 `origW == 0` 场景。本条降级为可维护性提示。
- **修复方向**：显式 `if (origW <= 0) return null;` 提前置零值防护，避免后续重构破坏短路。（改动面：小）

---

## `[Security]` 安全漏洞

> 排查范围：路径遍历、扩展名/MIME 双校验、Magic Number、md5 去重、上传目录可执行性、大小限制、缩略图库风险、storage_type、删除、绝对路径泄漏。逐项覆盖 §2.2 文件上传重点。

### [P2] [Security] SVG 等可执行/可 XSS 文件类型不在允许列表，但缺失显式黑名单与上传目录禁解析兜底 <!-- 编号：B05-05 -->
- **定位**：`FileAppService.java:59`（`allowed-extensions` 白名单 `jpg,jpeg,png,gif,webp,txt,md,pdf,zip,rar,7z`）；nginx `deploy/nginx/conf.d/default.conf:47-54`（`/uploads/` 仅反代，**无 `location ~ \.php$|\.jsp$|\.sh$` 禁解析**也无 `default_type` 兜底）
- **现象**：①白名单本身**不含** `svg/html/htm/js/jsp/php`，扩展名层已阻断典型 webshell；②但 nginx 对 `/uploads/` 段未显式禁脚本解析、未强制 `Content-Disposition: attachment` 或 `X-Content-Type-Options nosniff`（全局 `nosniff` 在 server 段 line 24 已加，但仅 header 提示，不阻止 SVG 内嵌脚本被浏览器执行）；③若运维误把 `/uploads/` 配成 root 直接服务，svg/html 会被当网页执行（存储型 XSS）。
- **影响**：当前白名单 + 反代到 backend + 全局 `nosniff` 三层叠加，实际可执行风险低。但 `pdf` 在白名单内，浏览器内联打开 PDF 可触发 JS；`svg` 一旦被加入白名单（用户提需求时常见）会直接成存储型 XSS 入口。
- **根因/分析**：白名单是主要防线，nginx 层缺独立兜底。已排除：当前不可直接利用（svg/html 不在白名单）。
- **修复方向**：①nginx `/uploads/` 段加 `location ~* \.(svg|html?|js)$ { return 403; }` 或对所有非图片类型 `add_header Content-Disposition "attachment"`；②ApplicationResponse 对 `application/pdf` 等内联风险类型强制下载头。（改动面：中）

### [P2] [Security] Magic Number 校验对 txt/md/zip/rar/7z 完全跳过，且 zip/rar/7z 等容器无内嵌文件名/路径校验 <!-- 编号：B05-06 -->
- **定位**：`FileAppService.java:176-200`（`isValidFileType`，`expected == null` 时直接 `return true`，即 line 183-184）；白名单含 `zip,rar,7z`（line 59）
- **现象**：txt/md/zip/rar/7z 在 `MAGIC_NUMBERS` map 中无条目（line 66-73 仅 jpg/jpeg/png/gif/pdf/webp），`isValidFileType` 对这些类型直接放行。压缩包内部的 `..` 路径条目（Zip Slip）、内嵌 webshell 文件名均不检测。
- **影响**：上传恶意 zip 包后，若未来有"解压"功能（当前无），会成 Zip Slip 入口；当前仅作为附件存储，风险有限。但 txt/md 可被注入恶意 markdown/HTML 片段，经前端渲染（关联 F03 markdown XSS）成攻击载体。
- **根因/分析**：Magic Number 表只覆盖常见图片/PDF，文档与压缩包无内容校验。MIME 校验（line 116-125）也只比对客户端传来的 `Content-Type` 字符串，可伪造。
- **修复方向**：①对 txt/md 限制最大解压后字节数 + 内容首字节非二进制；②未来引入解压时必须用 `Path.normalize()` + 起始目录断言防 Zip Slip；③MIME 不要信任客户端头，以扩展名 + Magic Number 推导为准。（改动面：中）

### [P2] [Security] ImageIO.read 未限制解码图片尺寸/像素总数，存在大图 OOM/DoS 风险 <!-- 编号：B05-07 -->
- **定位**：`ImageThumbnailService.java:42`（`ImageIO.read(new ByteArrayInputStream(fileData))`）
- **现象**：JDK `ImageIO` 默认不对 `getWidth * getHeight` 设上限。10MB 内（multipart 上限）的精心构造 PNG（高压缩比 + 巨大像素维度，如 50000×50000）解码后 BufferedImage 占用 `width*height*4` 字节可达数十 GB，触发 OOM 或 GC 抖动。`ImageIO.read` 也不防"解压炸弹"（decompression bomb）。
- **影响**：单管理员场景触发概率低，但任何能访问 `/api/admin/file/upload` 的会话（一旦 admin token 泄漏或 CSRF 命中）可一次请求打挂 JVM。Spring multipart 10MB 限制在**压缩字节**层，挡不住解码后的内存膨胀。
- **根因/分析**：无 `ImageReadParam` 设源区域、无 `ImageInputStream` 预读 header 限定 dimension。`javax.imageio` 默认无内存上限保护 [需查证：不同 JDK 版本行为]。
- **修复方向**：①读 header 前用 `ImageIO.getImageReaders` 取 `width/height`，超阈值（如 >8000px 任一边或 >50M 像素）直接拒；②或改用 `thumbnailator` / `img-scaled` 等带内存约束的库（pom 未引入，见 Deps）；③multipart 全局 `max-file-size` 可适当下调图片类上限。（改动面：中）

### [P3] [Security] 缩略图统一转 JPEG，GIF 动图/透明 PNG 信息丢失（功能性与潜在 ICC profile 解析风险） <!-- 编号：B05-08 -->
- **定位**：`ImageThumbnailService.java:57`（`BufferedImage.TYPE_INT_RGB`，无 alpha）、`line 71`（`ImageIO.write(thumbnail, "jpeg", bos)`）
- **现象**：①PNG 透明背景被铺成黑色（TYPE_INT_RGB 无 alpha 通道）；②GIF 动图只取首帧；③`ImageIO.read` 默认会解析嵌入的 ICC color profile，畸形 profile 历史 CVE（如 JDK-8309595 系）[需查证：项目 JDK 21 当前 patch 版本是否覆盖]。
- **影响**：主要功能缺陷（透明 PNG 缩略图变黑底），安全面为潜伏（依赖 JDK patch 水平，超出本模块代码）。
- **根因/分析**：刻意选 TYPE_INT_RGB + JPEG 减小缩略图体积，但牺牲了 alpha。
- **修复方向**：①透明 PNG 改输出 PNG/WebP 缩略图；②保持现状但记录已知限制。（改动面：小，纯体验）

---

## `[Arch]` 架构与技术债

> 排查范围：usage_type/ref_id/user_id 字段使用、storage_type 多态、缩略图后补接口设计、孤儿文件清理。共享对象（Sa-Token/逻辑删除/schema 双轨）按 §8.6 引用 B06/B15。

### [P1] [Arch] usage_type/ref_id/user_id 字段全链路空置，孤儿文件清理机制完全缺失 <!-- 编号：B05-09 -->
- **定位**：字段定义 `BlogFile.java:27-30`、schema `init.sql:366-369`/`schema.sql:384-387`；upload 赋值段 `FileAppService.java:152-166`；grep `setUsageType|setRefId|setUserId` on `BlogFile` 在整个 backend **零命中**
- **现象**：实体声明了 `userId/usageType/refId` 三个软引用字段（分别表示上传者、用途 article/project/avatar/log、关联对象 id），但 `upload()` 从不写入这三列；`delete()`、文章/项目/日志的 CRUD 也都不读取或维护。索引 `idx_file_user_id/idx_file_usage_type/idx_file_ref_id`（`schema.sql:409/411/412`）是死索引。
- **影响**：①**孤儿文件永久堆积**——上传后删除文章/项目，关联文件无人清理，磁盘只增不减（`delete()` 还显式注释"逻辑删除不删物理文件"，见 B05-10）；②无法追溯文件被谁上传、用在哪；③B05-03 的归属校验失去数据基础；④`idx_file_*` 三个索引白占空间且永远 0 命中。
- **根因/分析**：文件模块设计为通用上传中心 + 软引用，但消费侧（Article/Project/Skill 等）从未回写引用关系。CLAUDE.md 列的"自动优化闭环""日报系统"都不依赖此模块。**整个文件模块在生产中实际是孤岛**——`ArticleAppService` 不引用 `BlogFile`/`fileId`/`cover`（已 grep 确认），前端文件管理页仅供上传/查看/删除，不与任何业务实体绑定。
- **修复方向**：①若文件模块要保留：在 Article/Project/Skill 的 create/update 时回写 `usageType + refId`，delete 时清理或标记孤儿；upload 时写 `userId`；②若不保留：明确降级为"独立图床"，删除 usage_type/ref_id/user_id 字段与索引，简化模型。（改动面：大，跨模块；或 小，若选简化方向）

### [P2] [Arch] storage_type 声明 local/minio/oss 三态，代码硬编码 local，无切换抽象 <!-- 编号：B05-10 -->
- **定位**：`FileAppService.java:62-63`（`storage-type` 默认 `local`）、`line 161`（`blogFile.setStorageType(storageType)` 仅落库不分支）；schema 注释 `init.sql:386`（"local-本地 minio-Minio oss-阿里云OSS"）；磁盘写入硬编码 `Files.write` `line 142`
- **现象**：配置项 `blog.file.storage-type` 可填 `local/minio/oss`，但 `upload()` 永远走本地 `Files.write(targetPath, ...)`，填 `minio` 不会报错也不会切到对象存储，文件仍落本地、DB 记 `storage_type=minio` 的错误元数据。无 `StorageStrategy` 抽象。
- **影响**：运维误改 `storage-type=minio` 后，系统静默错误（文件在本地、DB 说在 minio），下载/访问 URL 仍指向 `/uploads/` 局部可发现，但元数据已脏。MVP 单机部署可接受，扩展到对象存储需重写。
- **根因/分析**：字段为"未来扩展"预留但无实现，违反 §1.2 最小变更精神（要么实现要么不声明）。
- **修复方向**：①MVP 阶段删掉 minio/oss 选项，配置项只接受 `local`，schema 注释更新；②或引入 `FileStorageStrategy` 接口 + `LocalStorage`/`OsStorage` 实现，按配置注入。（改动面：小，简化方向）

### [P3] [Arch] regenerate-thumbnails 管理接口每次只补 100 个，大批量需手动多次触发 <!-- 编号：B05-11 -->
- **定位**：`FileAppService.java:35`（`THUMBNAIL_REGEN_BATCH_SIZE = 100`）、`line 220-249`、`FileController.java:56-59`
- **现象**：缩略图后补接口固定取 100 个候选（`fileRepository.findImagesMissingThumbnail(100)`），处理完即返回。若历史有 1000 个无缩略图图片，管理员需手动点 10 次接口，无进度反馈、无后台异步任务。
- **影响**：可运维性差，但属低频运维场景（一次性历史数据迁移）。无任务对账（关联 B17）。
- **根因/分析**：批处理设计为同步单批，避免单请求 OOM，思路合理，但缺总计数与剩余提示。
- **修复方向**：返回 `{processed, remaining}` 让前端知道是否需再次触发；或改 `@Async` 后台全量跑。（改动面：小）

---

## `[Deps]` 依赖升级与版本

### 本模块依赖清单（基于声明文件，未翻依赖源码）

| 依赖 | 版本 | 声明位置 | 已知风险/可升级 | 备注 |
|---|---|---|---|---|
| `javax.imageio.ImageIO` / `java.awt.*` | JDK 内置 | JDK 21 | 见 B05-07/08（OOM、ICC profile 解析风险） | 无独立依赖，跟随 JDK |
| `org.springframework.util.DigestUtils`（md5） | Spring Boot 3.3.5 内置 | `FileAppService.java:5` | MD5 抗碰撞性弱（见 B05-12） | 用于去重而非安全，可接受 |
| `mybatis-plus-spring-boot3-starter` | 3.5.9 | `backend/pom.xml:41-42` | 关联 B14 | 提供逻辑删除/分页 |
| `sa-token-spring-boot3-starter` | 1.44.0 | `backend/pom.xml:60-61` | 关联 B06 | admin 拦截 |
| **缩略图专用库**（thumbnailator / imgscalr / twelvemonkeys） | **未引入** | — | 见 B05-07 | 项目用裸 `ImageIO`，无内存约束库兜底 |

> 排查范围：pom.xml 全量 + application.yml 配置。未发现第三方缩略图/文件上传增强库（如 commons-fileupload、thumbnailator），全部用 JDK 原生 + Spring multipart。

### [P3] [Deps] 使用裸 ImageIO 而非专用图像库，缺内存约束与格式支持 <!-- 编号：B05-12 -->
- **定位**：`ImageThumbnailService.java:6-9`（仅 import `javax.imageio` / `java.awt`）；`backend/pom.xml` 无 `thumbnailator`/`imgscalr`/`twelvemonkeys`
- **现象**：裸 ImageIO 无像素上限保护（B05-07）、对 CMYK JPEG / 部分 WebP 支持差、ICC profile 解析风险（B05-08）。
- **影响**：当前支持的 5 种格式（jpeg/png/gif/webp/bmp）覆盖 MVP 需求，但 webp 支持依赖 JDK 版本 [需查证：JDK 21 原生 webp 读支持情况]，CMYK JPEG 会解码异常。
- **根因/分析**：刻意避免引入额外依赖，符合最小变更。但安全/健壮性有缺口。
- **修复方向**：评估引入 `net.coobird:thumbnailator`（轻量、带尺寸约束）或 `com.twelvemonkeys.imageio`（格式支持更全）。（改动面：中，新增依赖需评审）

---

## `[Design]` 功能设计合理性

> 从真实使用出发，回答 §2.5 中相关问题（场景适配、闭环完整性、可运维性、MVP 假设检验）。

**审视结论**：

1. **场景适配（§2.5.1）**：文件模块对"单人维护的技术博客 + 每工作日 AI 日报"场景**过度设计**。预留了 minio/oss 多存储、usage_type 四种用途软引用、user_id 归属，但实际：①文章不引用文件（ArticleAppService 零调用 BlogFile）；②永远只 local；③无多用户。**整套机制是空转的图床**，仅前端管理页用得上。MVP 阶段更合理的是"文章封面上传 + Markdown 内嵌图片"两个具体场景驱动，而非通用文件中心。

2. **闭环完整性（§2.5.2）**：**不形成闭环**。上传 → 列表 → 删除是开环，没有任何业务实体消费这些文件（B05-09）。删除文章不会清理其引用的图片（因为根本没引用关系），孤儿文件只能靠管理员在文件管理页手动删除。md5 去重设计合理，但因 B05-01 无 DB 约束、B05-02 容错缺失，去重本身也脆弱。

3. **可运维性（§2.5.3）**：缩略图后补接口（`/admin/file/regenerate-thumbnails`）是唯一的运维工具，批 100 无进度提示（B05-11）。无文件清理任务、无磁盘占用监控、无孤儿检测。`delete` 物理文件不删（B05-10 注释明示），磁盘只增不减，长期运行需人工介入。

### [P2 / Design] [Design] 文件模块整体定位需明确：保留并补闭环，还是降级为最小图床 <!-- 编号：B05-13 -->
- **定位**：整个模块（`application/file/`、`domain/file/`、`interfaces/rest/FileController`、`sys_file` 表、前端 `/admin/file`）
- **现象**：文件模块功能完整（上传/校验/缩略图/去重/列表/删除都实现），但**无任何业务消费方**，预留的 usage_type/ref_id/user_id/storage_type 多态能力全部空置（B05-09/B05-10）。
- **影响**：维护成本（schema 字段、索引、代码路径、安全校验）持续支出，但业务价值为零。安全面反而因模块存在而扩大（上传入口、ImageIO OOM、路径校验等都需要持续维护）。
- **建议方向**：二选一——
  - **A. 补闭环**（改动面：大）：让 Article/Project/DailyLog 在编辑时选择封面/配图，回写 usage_type+ref_id；upload 写 user_id；增加孤儿文件清理定时任务（关联 B17）。
  - **B. 降级简化**（改动面：中）：删除 usage_type/ref_id/user_id/storage_type 字段与索引，文档明确"本模块是 Markdown 内嵌图片图床，不做业务绑定"，保留 md5 去重 + 缩略图即可。
- **关联**：B05-09、B05-10、B05-03（决策直接影响多条 Arch/Security 发现的处置）

---

## 模块小结

### 严重度统计

| 级别 | 数量 | 条目编号 |
|---|---|---|
| P0 | 0 | — |
| P1 | 1 | B05-09 |
| P2 | 7 | B05-01, B05-02, B05-03, B05-05, B05-06, B05-07, B05-13 |
| P3 | 4 | B05-04, B05-08, B05-11, B05-12 |
| P4 | 0 | — |

### Top 风险（本模块最该先看的 ≤3 条）

1. **B05-09 usage_type/ref_id/user_id 全链路空置，孤儿文件清理缺失** —— 整个模块无业务消费方，是定位其他所有发现的前置决策点（决定保留还是简化）。
2. **B05-01 + B05-02 md5 去重无 DB 唯一约束 + selectOne 多行抛异常** —— 一旦并发上传产生重复 md5，去重查询会让整个 upload 链路 500，需人工清库。
3. **B05-07 ImageIO 无内存约束，大图可致 OOM** —— 单请求可打挂 JVM，是本模块最实质的安全风险（其他安全项多被白名单 + 反代兜住）。

### 修复优先级建议

- **立即**（P1）：B05-09（先做设计决策 A/B，决定后续所有修复走向）
- **应尽快**（P2，决策后）：
  - 若选 A（补闭环）：B05-03（归属校验）、B05-13（执行补引用）
  - 若选 B（简化）：B05-10（删 storage_type 选项）、B05-09 简化字段
  - 不论 A/B：B05-01 + B05-02（md5 唯一约束 + selectOne 容错）、B05-07（ImageIO 尺寸上限）
- **计划**（P2）：B05-05（nginx 上传目录禁解析）、B05-06（压缩包校验）
- **择机**（P3）：B05-04、B05-08、B05-11、B05-12

### 排查盲区 / 待复核

- **[需查证]** JDK 21 原生 `ImageIO` 对 WebP 读取的实际支持情况（B05-12）——本次未跑 `ImageIO.getReaderFormatNames()` 验证，命令边界 §1.3 禁止运行 JVM。
- **[需查证]** JDK 21 当前 patch 版本是否覆盖 ICC profile 解析相关 CVE（B05-08）——需对照项目实际 JDK 发行版与 CVE 数据库。
- **[需查证]** md5 去重在逻辑删除下的预期语义——当前 `findByMd5` 配合 `@TableLogic` 自动过滤已删记录，软删后同 md5 可重传。是否符合产品预期（用户删除后能否重传同文件）需产品确认（B05-01 修复方向依赖此）。
- **未覆盖**：本次未深查前端 `/admin/file/Index.vue` 完整交互（仅读前 60 行确认有删除按钮），前端上传大小预检、错误提示等体验问题留待 F04 评估。
- **引用而非深查**：Sa-Token admin 拦截规则（`/api/admin/file/**` 已被 `/api/admin/**` 覆盖，见 B06）、`@TableLogic` 全局配置（见 B14/B15）、CORS（见 B16）。
