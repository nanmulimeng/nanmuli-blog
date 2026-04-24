# Nanmuli Blog

> 个人技术博客系统 - 基于 DDD 架构的现代化博客平台

<p align="center">
  <img src="https://img.shields.io/badge/Spring%20Boot-3.3.5-6DB33F?logo=springboot" alt="Spring Boot">
  <img src="https://img.shields.io/badge/Java-21-007396?logo=openjdk" alt="Java">
  <img src="https://img.shields.io/badge/Vue-3.4-4FC08D?logo=vue.js" alt="Vue">
  <img src="https://img.shields.io/badge/TypeScript-5.3-3178C6?logo=typescript" alt="TypeScript">
  <img src="https://img.shields.io/badge/PostgreSQL-15+-336791?logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Redis-7+-DC382D?logo=redis" alt="Redis">
</p>

---

## 项目简介

Nanmuli Blog 是一个基于 **DDD（领域驱动设计）** 架构的个人技术博客系统，采用前后端分离设计，专注于技术文章分享、技术日志记录和个人技能展示。

### 核心特性

- **DDD 架构**：清晰的领域层、应用层、接口层、基础设施层分离
- **Markdown 编辑器**：支持代码高亮、实时预览
- **文章管理**：发布/草稿/回收站状态，置顶功能
- **技术日志**：快速记录每日技术学习
- **Web采集器**：网页采集、深度爬取、关键词搜索、AI内容整理
- **数据统计**：独立访客(UV)、页面浏览(PV)统计
- **主题切换**：支持明暗主题
- **响应式设计**：适配桌面端和移动端
- **Docker部署**：一键容器化部署，含Python爬虫微服务

---

## 技术栈

### 后端

| 技术 | 版本 | 说明 |
|------|------|------|
| Spring Boot | 3.3.5 | 核心框架 |
| Java | 21 LTS | 编程语言 |
| MyBatis Plus | 3.5.9 | ORM框架 |
| PostgreSQL | 15+ | 主数据库 |
| Redis | 7+ | 缓存/会话 |
| Sa-Token | 1.44.0 | 认证授权 |
| Knife4j | 4.4.0 | API文档 |
| Hutool | 5.8.36 | 工具库 |
| DashScope | Qwen 3.6-plus | AI内容整理（OpenAI兼容端点）|

### 爬虫服务

| 技术 | 版本 | 说明 |
|------|------|------|
| Python FastAPI | 0.100+ | 爬虫Web框架 |
| Crawl4AI | 0.8.x | 无头Chromium爬虫 |

### 前端

| 技术 | 版本 | 说明 |
|------|------|------|
| Vue | 3.4.15 | 前端框架 |
| Vite | 5.0.11 | 构建工具 |
| TypeScript | 5.3.3 | 类型系统 |
| Element Plus | 2.5.1 | UI组件库 |
| Pinia | 2.1.7 | 状态管理 |
| Tailwind CSS | 3.4.1 | CSS框架 |
| md-editor-v3 | 4.11.0 | Markdown编辑器 |

---

## 快速开始

### 环境要求

- JDK 21+
- Node.js 18+
- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- Maven 3.8+

### 1. 克隆项目

```bash
git clone https://github.com/nanmuli/nanmuli-blog.git
cd nanmuli-blog
```

### 2. 数据库初始化

```bash
# 创建数据库
createdb nanmuli_blog

# 执行初始化脚本（位于 backend/src/main/resources/db/）
psql -d nanmuli_blog -f backend/src/main/resources/db/init.sql
```

### 3. 启动后端

```bash
cd backend

# 修改配置文件
# 复制 application-dev.yml 并修改数据库连接信息

# 运行
mvn spring-boot:run
```

后端服务默认运行在 `http://localhost:8081`

API文档：`http://localhost:8081/doc.html`

### 4. 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev
```

前端服务默认运行在 `http://localhost:5173`

### 5. 登录

默认管理员账号：
- 用户名：`admin`
- 密码：`admin123`

---

## 项目结构

```
nanmuli-blog/
├── backend/                     # 后端项目
│   ├── src/main/java/com/nanmuli/blog/
│   │   ├── domain/             # 领域层 - 实体、值对象、仓储接口
│   │   ├── application/        # 应用层 - 应用服务、DTO、Command
│   │   ├── interfaces/         # 接口层 - Controller、Filter
│   │   ├── infrastructure/     # 基础设施层 - Mapper、配置
│   │   └── shared/             # 共享内核 - 工具类、异常
│   └── pom.xml
│
├── frontend/                    # 前端项目
│   ├── src/
│   │   ├── api/                # API接口
│   │   ├── components/         # 组件
│   │   ├── views/              # 页面
│   │   ├── stores/             # 状态管理
│   │   └── utils/              # 工具函数
│   └── package.json
│
├── crawler-service/             # Python爬虫服务
│   ├── crawler/                # Crawl4AI爬虫模块
│   │   ├── api.py             # FastAPI路由
│   │   ├── single.py          # 单页爬取
│   │   ├── deep.py            # 深度爬取
│   │   └── search.py          # 关键词搜索
│   ├── requirements.txt
│   └── Dockerfile
│
├── docs/                        # 项目文档
│   └── project-plan.md         # 开发方案
│
└── deploy/                      # 部署配置
```

---

## 主要功能

### 文章管理
- Markdown 编辑器，支持代码高亮
- 文章状态：发布/草稿/回收站
- 置顶功能
- 自动生成摘要和阅读时间
- 分类关联（仅叶子分类）

### 技术日志
- 快速记录每日技术笔记
- 时间线展示
- 心情/天气标记

### 个人展示
- 技能云展示
- 项目展示
- 关于页面

### 数据统计
- 文章浏览量（PV）
- 独立访客统计（UV）
- 仪表盘数据可视化

### Web采集器
- 单页采集：输入URL自动抓取并整理
- 深度爬取：BFS多页爬取，可配置深度和页数上限
- 关键词搜索：多搜索引擎支持，自动爬取搜索结果
- AI内容整理：DashScope Qwen模型智能整理为结构化文章
- 一键转换：采集结果转为文章草稿或技术日志
- 去重机制：30天URL去重 + 内容哈希去重

### 系统功能
- 用户认证（Sa-Token）
- 文件上传
- 系统配置
- 主题切换

---

## 部署

### 生产环境配置

1. **修改配置文件**
   - `backend/src/main/resources/application-prod.yml`

2. **构建后端**
   ```bash
   cd backend
   mvn clean package -DskipTests
   ```

3. **构建前端**
   ```bash
   cd frontend
   npm run build
   ```

4. **部署目录结构**
   ```
   /opt/nanmuli-blog/
   ├── blog-backend.jar      # 后端jar包
   ├── uploads/              # 文件上传目录
   ├── logs/                 # 日志目录
   └── dist/                 # 前端构建产物
   ```

   **创建目录并设置权限**：
   ```bash
   sudo mkdir -p /opt/nanmuli-blog/{uploads,logs}
   sudo chown -R nanmuli:nanmuli /opt/nanmuli-blog
   ```

5. **Nginx 配置示例**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;
       
       # 前端静态资源
       location / {
           root /opt/nanmuli-blog/dist;
           try_files $uri $uri/ /index.html;
       }
       
       # 后端API代理
       location /api/ {
           proxy_pass http://localhost:8081/api/;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

6. **Systemd 服务配置**
   ```bash
   # /etc/systemd/system/nanmuli-blog.service
   [Unit]
   Description=Nanmuli Blog Backend
   After=network.target
   
   [Service]
   Type=simple
   User=nanmuli
   WorkingDirectory=/opt/nanmuli-blog
   ExecStart=/usr/bin/java -Xms256m -Xmx512m -jar blog-backend.jar
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```

---

## 开发规范

### 后端规范
- 遵循 DDD 分层架构
- 领域层定义业务规则
- 应用层编排用例
- 接口层处理 HTTP 请求
- 使用构造器注入依赖

### 前端规范
- 使用 Composition API
- 组件名大驼峰
- 组合式函数使用 `use` 前缀
- API 接口统一管理

---

## 文档

- [开发方案](./docs/project-plan.md) - 详细的项目架构设计文档
- [Web采集器设计](./docs/web-collector-module-design.md) - WebCollector模块设计文档

---

## 常见问题排查

### 后端启动失败

**问题**：`Connection refused` 数据库连接错误
- **解决**：检查PostgreSQL是否启动，数据库`nanmuli_blog`是否已创建

**问题**：`Redis connection failed`
- **解决**：检查Redis服务是否启动，或修改`application-dev.yml`中的Redis配置

**问题**：端口8081被占用
- **解决**：修改`application.yml`中的`server.port`配置

### 前端构建失败

**问题**：`Cannot find module`
- **解决**：删除`node_modules`目录，重新执行`npm install`

**问题**：`vite: not found`
- **解决**：确保Node.js版本>=18，重新安装依赖

### 生产部署问题

**问题**：文件上传失败
- **解决**：确保`/opt/nanmuli-blog/uploads`目录存在且有写入权限

**问题**：API请求404
- **解决**：检查Nginx配置中的`proxy_pass`端口是否与后端服务一致（默认8081）

**问题**：静态资源加载失败
- **解决**：检查Nginx的`root`路径是否指向正确的`dist`目录

## Docker 部署（推荐）

项目已全面支持 Docker 容器化部署，包含所有服务的一键启动。

### 系统要求

- Docker 20.10+
- Docker Compose 2.0+
- 内存：最低 2GB（推荐 4GB）

### 快速启动

```bash
# 1. 克隆项目
git clone <repository-url>
cd nanmuli-blog

# 2. 执行部署脚本
bash deploy/deploy.sh

# 3. 或直接使用 Docker Compose
docker-compose up -d
```

### 服务架构

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │   Nginx     │  │   Backend   │  │    Crawler      │  │
│  │  (前端)      │  │  (Java)     │  │ (Python/Crawl4AI)│  │
│  │   :80       │  │   :8081     │  │    :8500        │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────┘  │
│         │                │                                │
│         └────────────────┼────────────────┐               │
│                          ▼                ▼               │
│                   ┌─────────────┐  ┌─────────────┐       │
│                   │  PostgreSQL │  │    Redis    │       │
│                   │    :5432    │  │    :6379    │       │
│                   └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### 服务说明

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| Nginx | nanmuli-frontend | 80 | 前端静态资源 + 反向代理 |
| Backend | nanmuli-backend | 8081 | Spring Boot 后端服务 |
| Crawler | nanmuli-crawler | 8500 | Python 爬虫服务 (Crawl4AI) |
| PostgreSQL | nanmuli-postgres | 5433 | 主数据库（映射到宿主机5433）|
| Redis | nanmuli-redis | 6380 | 缓存/会话（映射到宿主机6380）|

### 常用命令

```bash
# 查看所有服务状态
docker-compose ps

# 查看日志
docker-compose logs -f [service_name]

# 停止所有服务
docker-compose down

# 重启单个服务
docker-compose restart backend

# 进入容器调试
docker exec -it nanmuli-backend bash
docker exec -it nanmuli-crawler sh
```

### 爬虫服务单独部署

如果只需部署爬虫服务：

```bash
cd crawler-service
docker build -t nanmuli-crawler .
docker run -d -p 8500:8500 --name nanmuli-crawler nanmuli-crawler
```

---

## 许可证

[MIT License](./LICENSE)

---

<p align="center">
  Made with by <a href="https://github.com/nanmuli">nanmuli</a>
</p>
