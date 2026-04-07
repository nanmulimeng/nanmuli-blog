# PostgreSQL 使用教程与功能详解

---

## 目录

1. [PostgreSQL 简介](#第1章-postgresql-简介)
2. [安装与配置](#第2章-安装与配置)
3. [基础 SQL 操作](#第3章-基础-sql-操作)
4. [数据类型详解](#第4章-数据类型详解)
5. [索引与优化](#第5章-索引与优化)
6. [高级特性](#第6章-高级特性)
7. [复制与高可用](#第7章-复制与高可用)
8. [性能调优与最佳实践](#第8章-性能调优与最佳实践)
9. [PostgreSQL 16/17 新特性](#第9章-postgresql-1617-新特性)
10. [常见问题与解决方案](#第10章-常见问题与解决方案)

---

## 第1章 PostgreSQL 简介

### 1.1 什么是 PostgreSQL

PostgreSQL（通常简称为 Postgres）是世界上最先进的开源关系型数据库管理系统（RDBMS）。它起源于加州大学伯克利分校的 POSTGRES 项目，于 1986 年开始开发，1996 年更名为 PostgreSQL。

PostgreSQL 以其可靠性、功能丰富性和对 SQL 标准的严格遵守而闻名，被广泛应用于各种规模的应用程序，从小型 Web 应用到大型企业级系统。

### 1.2 核心特性

#### 1.2.1 符合 SQL 标准

PostgreSQL 是 SQL 标准最符合的开源数据库之一，支持 SQL:2016 标准的大部分特性：

- 完整的 ACID 事务支持
- 外键约束
- 连接（JOIN）
- 视图（Views）
- 子查询
- 触发器（Triggers）
- 存储过程

#### 1.2.2 高级数据类型支持

```sql
-- 数组类型
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    tags TEXT[],
    scores INT[]
);

-- JSON/JSONB 类型
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_data JSONB
);

-- 几何类型
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    point POINT,
    polygon POLYGON
);

-- 范围类型
CREATE TABLE reservations (
    id SERIAL PRIMARY KEY,
    room_number INT,
    during TSRANGE
);
```

#### 1.2.3 扩展性和可定制性

PostgreSQL 提供了强大的扩展机制：

```sql
-- 安装扩展
CREATE EXTENSION IF NOT EXISTS postgis;        -- 地理空间扩展
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- 模糊搜索扩展
CREATE EXTENSION IF NOT EXISTS uuid-ossp;      -- UUID 生成扩展
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- SQL 统计扩展
CREATE EXTENSION IF NOT EXISTS hstore;         -- 键值对存储扩展
```

#### 1.2.4 并发控制

PostgreSQL 使用多版本并发控制（MVCC）来实现高并发：

```sql
-- 事务隔离级别示例
BEGIN ISOLATION LEVEL READ COMMITTED;
SELECT * FROM accounts WHERE balance > 1000;
COMMIT;

BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT * FROM accounts WHERE balance > 1000;
-- 在事务期间，即使其他事务修改了数据，这里看到的数据保持一致
COMMIT;

BEGIN ISOLATION LEVEL SERIALIZABLE;
-- 最严格的隔离级别
COMMIT;
```

### 1.3 应用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| Web 应用 | 作为后端数据库存储用户数据、会话等 | 电商网站、社交平台 |
| 地理信息系统 | 结合 PostGIS 扩展处理空间数据 | 地图服务、物流追踪 |
| 数据仓库 | 支持复杂查询和分析 | BI 系统、报表平台 |
| 时序数据 | 存储时间序列数据 | IoT 设备监控、日志分析 |
| 金融系统 | 强一致性保证 | 银行核心系统、支付平台 |
| AI/ML | 向量存储和相似度搜索 | 推荐系统、语义搜索 |

### 1.4 PostgreSQL vs 其他数据库

| 特性 | PostgreSQL | MySQL | Oracle | SQL Server |
|------|------------|-------|--------|------------|
| 开源 | 是（BSD 许可） | 是（GPL） | 否 | 否 |
| 成本 | 免费 | 免费 | 高昂 | 中等 |
| SQL 标准符合度 | 最高 | 中等 | 高 | 高 |
| JSON 支持 | 原生 JSONB | JSON | 原生 JSON | JSON |
| 扩展性 | 极强 | 中等 | 强 | 中等 |
| 地理空间 | PostGIS | 有限 | Spatial | 有限 |
| 并发性能 | 优秀 | 良好 | 优秀 | 优秀 |

---

## 第2章 安装与配置

### 2.1 包管理器安装（APT）

#### 2.1.1 Ubuntu/Debian 系统

```bash
# 添加 PostgreSQL 官方仓库
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'

# 导入仓库签名密钥
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# 更新包列表
sudo apt-get update

# 安装 PostgreSQL 17
sudo apt-get install postgresql-17

# 或者安装 PostgreSQL 16
sudo apt-get install postgresql-16

# 安装附加组件
sudo apt-get install postgresql-contrib
```

#### 2.1.2 启动和管理服务

```bash
# 启动 PostgreSQL 服务
sudo systemctl start postgresql

# 设置开机自启
sudo systemctl enable postgresql

# 查看服务状态
sudo systemctl status postgresql

# 重启服务
sudo systemctl restart postgresql

# 停止服务
sudo systemctl stop postgresql
```

### 2.2 源码编译安装

#### 2.2.1 安装依赖

```bash
# CentOS/RHEL
sudo yum install -y gcc gcc-c++ make libicu-devel bison flex \
    readline-devel zlib-devel openssl-devel systemd-devel

# Ubuntu/Debian
sudo apt-get install -y build-essential libicu-dev bison flex \
    libreadline-dev zlib1g-dev libssl-dev libsystemd-dev
```

#### 2.2.2 下载并编译

```bash
# 下载源码
cd /usr/local/src
wget https://ftp.postgresql.org/pub/source/v17.5/postgresql-17.5.tar.gz
tar -xzf postgresql-17.5.tar.gz
cd postgresql-17.5

# 配置编译选项
./configure \
    --prefix=/data/pgsql \
    --with-openssl \
    --with-pgport=5432 \
    --with-systemd \
    --enable-nls \
    --with-icu \
    --with-libxml \
    --with-libxslt

# 编译并安装
make -j$(nproc)
sudo make install

# 创建 postgres 用户
sudo useradd -r -s /bin/bash -d /data/pgsql -m postgres

# 创建数据目录
sudo mkdir -p /data/pgsql/data
sudo chown postgres:postgres /data/pgsql/data

# 初始化数据库
sudo -u postgres /data/pgsql/bin/initdb -D /data/pgsql/data -E UTF8
```

#### 2.2.3 创建 systemd 服务

```bash
# 创建服务文件
sudo tee /etc/systemd/system/postgresql.service > /dev/null <<EOF
[Unit]
Description=PostgreSQL database server
After=network.target

[Service]
Type=forking
User=postgres
Group=postgres
Environment=PGDATA=/data/pgsql/data
ExecStart=/data/pgsql/bin/pg_ctl start -D \${PGDATA}
ExecStop=/data/pgsql/bin/pg_ctl stop -D \${PGDATA}
ExecReload=/data/pgsql/bin/pg_ctl reload -D \${PGDATA}
TimeoutSec=300

[Install]
WantedBy=multi-user.target
EOF

# 重新加载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2.3 Docker 安装

#### 2.3.1 使用官方镜像

```bash
# 拉取 PostgreSQL 17 镜像
docker pull postgres:17

# 拉取带 pgvector 扩展的镜像（用于向量搜索）
docker pull pgvector/pgvector:pg17

# 运行容器
docker run -d \
    --name postgres17 \
    -e POSTGRES_PASSWORD=your_password \
    -e POSTGRES_USER=admin \
    -e POSTGRES_DB=mydb \
    -p 5432:5432 \
    -v /data/postgres:/var/lib/postgresql/data \
    postgres:17

# 查看容器日志
docker logs postgres17

# 进入容器
docker exec -it postgres17 psql -U admin -d mydb
```

#### 2.3.2 使用 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:17
    container_name: postgres17
    environment:
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: your_secure_password
      POSTGRES_DB: myapp
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - ./postgres-data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - postgres-network
    restart: unless-stopped
    command: >
      postgres
      -c max_connections=300
      -c shared_buffers=2GB
      -c effective_cache_size=6GB
      -c work_mem=64MB

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@example.com
      PGADMIN_DEFAULT_PASSWORD: admin123
    ports:
      - "8080:80"
    networks:
      - postgres-network
    depends_on:
      - postgres

networks:
  postgres-network:
    driver: bridge
```


### 2.1 Windows安装

**使用官方安装程序**

1. 访问PostgreSQL官方下载页面：https://www.postgresql.org/download/windows/
2. 下载适用于Windows的安装程序（由EnterpriseDB提供）
3. 运行安装程序，按向导提示完成安装

```powershell
# 安装完成后，PostgreSQL服务会自动启动
# 可以通过服务管理器查看状态
Get-Service postgresql*

# 使用psql连接数据库（需要添加到PATH）
psql -U postgres -h localhost
```

**安装选项说明**
- 安装目录：默认为 `C:\Program Files\PostgreSQL\16`
- 数据目录：默认为 `C:\Program Files\PostgreSQL\16\data`
- 超级用户密码：安装过程中设置postgres用户密码
- 端口号：默认为5432

**Chocolatey安装（推荐开发者）**

```powershell
# 以管理员身份运行PowerShell
choco install postgresql

# 安装完成后初始化数据库
& "C:\Program Files\PostgreSQL\16\bin\initdb.exe" -D "C:\Program Files\PostgreSQL\16\data" -U postgres
```


### 2.2 macOS安装

**使用Homebrew安装（推荐）**

Homebrew是macOS上最流行的包管理器，安装PostgreSQL非常简单：

```bash
# 安装PostgreSQL
brew install postgresql@16

# 添加到PATH（根据Shell类型选择）
echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc

# 启动服务
brew services start postgresql@16

# 验证安装
psql --version

# 创建默认数据库（使用当前用户名）
createdb $(whoami)

# 连接数据库
psql
```

**使用Postgres.app**

Postgres.app是macOS上另一个流行的安装方式，提供图形化界面：

1. 访问 https://postgresapp.com/ 下载应用
2. 将Postgres.app拖入Applications文件夹
3. 双击启动，点击"Initialize"创建服务器
4. 点击"Open psql"即可使用命令行工具


### 2.4 核心配置参数

#### 2.4.1 postgresql.conf 主要配置

```ini
# 连接和认证
listen_addresses = '*'          # 监听所有网络接口
port = 5432                     # 监听端口
max_connections = 300           # 最大连接数
superuser_reserved_connections = 3  # 为超级用户保留的连接数

# 内存配置
shared_buffers = 4GB            # 共享缓冲区（建议为内存的25%）
effective_cache_size = 12GB     # 操作系统缓存大小估计
work_mem = 64MB                 # 每个查询操作的内存
maintenance_work_mem = 1GB      # 维护操作（VACUUM、CREATE INDEX）的内存

# WAL 配置
wal_buffers = 16MB              # WAL 缓冲区大小
wal_level = replica             # WAL 级别（minimal, replica, logical）
max_wal_size = 4GB              # 最大 WAL 文件大小
min_wal_size = 1GB              # 最小 WAL 文件大小
checkpoint_completion_target = 0.9  # 检查点完成目标

# 查询规划器
effective_io_concurrency = 200  # 并发磁盘 I/O 操作数
random_page_cost = 1.1          # 随机页面访问成本（SSD 建议 1.1）

# 日志配置
logging_collector = on          # 启用日志收集
log_directory = 'log'           # 日志目录
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d           # 日志轮转周期
log_rotation_size = 100MB       # 日志文件大小限制
log_min_duration_statement = 1000   # 记录执行超过 1 秒的查询

# 自动清理
autovacuum = on                 # 启用自动清理
autovacuum_max_workers = 3      # 自动清理工作进程数
autovacuum_naptime = 1min       # 自动清理间隔
```

#### 2.4.2 pg_hba.conf 访问控制

```ini
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# 本地连接使用 Unix 域套接字
local   all             all                                     peer

# IPv4 本地连接
host    all             all             127.0.0.1/32            scram-sha-256

# IPv6 本地连接
host    all             all             ::1/128                 scram-sha-256

# 允许特定网段访问
host    all             all             192.168.1.0/24          scram-sha-256
host    all             all             10.0.0.0/8              scram-sha-256

# 允许特定用户从任何地方访问特定数据库
host    mydb            myuser          0.0.0.0/0               scram-sha-256

# 拒绝特定 IP 访问
host    all             all             192.168.1.100/32        reject
```

#### 2.4.3 配置重载

```sql
-- 查看当前配置
SHOW shared_buffers;
SHOW max_connections;

-- 修改配置（需要重启）
ALTER SYSTEM SET shared_buffers = '8GB';

-- 修改配置（不需要重启）
ALTER SYSTEM SET work_mem = '128MB';
SELECT pg_reload_conf();

-- 查看配置文件位置
SHOW config_file;
SHOW hba_file;
SHOW data_directory;
```

---

## 第3章 基础 SQL 操作

### 3.1 数据库管理

```sql
-- 创建数据库
CREATE DATABASE mydb
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TABLESPACE = pg_default
    CONNECTION LIMIT = 100;

-- 连接到数据库
\c mydb

-- 查看所有数据库
\l
SELECT datname FROM pg_database WHERE datistemplate = false;

-- 删除数据库
DROP DATABASE IF EXISTS mydb;

-- 重命名数据库
ALTER DATABASE mydb RENAME TO newdb;

-- 创建表空间
CREATE TABLESPACE fastspace
    LOCATION '/ssd/postgresql/data';
```


### 3.1 psql命令行工具

psql是PostgreSQL自带的交互式命令行工具，是数据库管理员和开发者的必备工具。

**连接与退出**

```bash
# 连接到数据库
psql -U postgres -d mydb

# 在psql中切换数据库
\c mydb
\c mydb username@hostname

# 退出psql
\q
# 或使用快捷键 Ctrl+D
```

**数据库相关命令**

```sql
-- 列出所有数据库
\l
\l+  -- 显示更多信息（大小、表空间等）

-- 显示当前数据库信息
\conninfo

-- 创建数据库
CREATE DATABASE mydb;

-- 删除数据库
DROP DATABASE mydb;

-- 重命名数据库
ALTER DATABASE mydb RENAME TO newdb;
```

**表相关命令**

```sql
-- 列出当前数据库的所有表
\dt
\dt *.*       -- 显示所有schema的表
\dt+          -- 显示更多信息（大小、描述等）

-- 查看表结构
\d tablename
\d+ tablename -- 显示更多详细信息

-- 列出所有schema
\dn
\dn+          -- 显示更多详细信息

-- 列出所有视图
\dv

-- 列出所有序列
\ds

-- 列出所有索引
\di

-- 列出所有函数
\df

-- 列出所有触发器
\dT
```

**用户和权限命令**

```sql
-- 列出所有用户/角色
\du
\du+          -- 显示更多详细信息

-- 列出所有表空间
\db

-- 显示当前用户
SELECT current_user;
```

**实用命令**

```sql
-- 执行SQL文件
\i /path/to/script.sql

-- 将查询结果保存到文件
\o /path/to/output.txt
SELECT * FROM users;
\o  -- 停止输出到文件

-- 设置输出格式
\x on         -- 扩展显示（每行一个字段）
\x off        -- 表格显示
\x auto       -- 根据宽度自动选择

-- 设置输出格式
\a            -- 对齐/不对齐模式切换
\H on         -- HTML格式输出
\t on         -- 只显示数据，不显示表头

-- 设置分页器
\pset pager off    -- 关闭分页
\pset pager on     -- 开启分页

-- 设置NULL显示
\pset null '(null)'

-- 显示执行时间
\timing on

-- 查看变量
\set          -- 显示所有变量
\set VARNAME value   -- 设置变量
\echo :VARNAME       -- 显示变量值

-- 获取帮助
\?            -- psql命令帮助
\h            -- SQL命令帮助
\h CREATE TABLE   -- 特定命令的帮助
```

**快捷查询**

```sql
-- 查看当前数据库大小
SELECT pg_size_pretty(pg_database_size(current_database()));

-- 查看表大小
SELECT pg_size_pretty(pg_total_relation_size('tablename'));

-- 查看所有表的大小（按大小排序）
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 查看当前活动连接
SELECT * FROM pg_stat_activity;

-- 查看锁信息
SELECT * FROM pg_locks;
```


### 3.2 表操作（DDL）

#### 3.2.1 创建表

```sql
-- 基本表创建
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hire_date DATE NOT NULL DEFAULT CURRENT_DATE,
    salary NUMERIC(12, 2) CHECK (salary > 0),
    department_id INTEGER REFERENCES departments(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 带注释的表创建
COMMENT ON TABLE employees IS '员工信息表';
COMMENT ON COLUMN employees.id IS '员工唯一标识';
COMMENT ON COLUMN employees.email IS '员工邮箱地址';

-- 创建临时表（会话结束自动删除）
CREATE TEMP TABLE temp_employees AS
SELECT * FROM employees WHERE 1=0;

-- 创建表并填充数据
CREATE TABLE high_earners AS
SELECT * FROM employees WHERE salary > 100000;
```

#### 3.2.2 修改表结构

```sql
-- 添加列
ALTER TABLE employees ADD COLUMN phone VARCHAR(20);
ALTER TABLE employees ADD COLUMN address TEXT DEFAULT 'Unknown';

-- 修改列类型
ALTER TABLE employees ALTER COLUMN salary TYPE NUMERIC(15, 2);

-- 重命名列
ALTER TABLE employees RENAME COLUMN phone TO mobile_phone;

-- 删除列
ALTER TABLE employees DROP COLUMN IF EXISTS temp_column;

-- 添加约束
ALTER TABLE employees ADD CONSTRAINT chk_salary_positive 
    CHECK (salary > 0);

ALTER TABLE employees ADD CONSTRAINT fk_department
    FOREIGN KEY (department_id) REFERENCES departments(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE;

-- 删除约束
ALTER TABLE employees DROP CONSTRAINT IF EXISTS chk_salary_positive;

-- 重命名表
ALTER TABLE employees RENAME TO staff;
```

#### 3.2.3 删除表

```sql
-- 删除表
DROP TABLE IF EXISTS temp_employees;

-- 级联删除（删除外键引用）
DROP TABLE IF EXISTS departments CASCADE;

-- 截断表（快速清空，不可回滚）
TRUNCATE TABLE temp_logs;
TRUNCATE TABLE logs, log_details RESTART IDENTITY CASCADE;
```

### 3.3 数据操作（DML）

#### 3.3.1 插入数据

```sql
-- 单行插入
INSERT INTO employees (first_name, last_name, email, salary, department_id)
VALUES ('John', 'Doe', 'john.doe@example.com', 75000.00, 1);

-- 多行插入
INSERT INTO employees (first_name, last_name, email, salary, department_id)
VALUES 
    ('Jane', 'Smith', 'jane.smith@example.com', 80000.00, 2),
    ('Bob', 'Johnson', 'bob.johnson@example.com', 65000.00, 1),
    ('Alice', 'Williams', 'alice.w@example.com', 90000.00, 3);

-- 插入并返回生成的值
INSERT INTO employees (first_name, last_name, email, salary)
VALUES ('Charlie', 'Brown', 'charlie@example.com', 70000.00)
RETURNING id, created_at;

-- 从其他表插入
INSERT INTO employees_archive
SELECT * FROM employees WHERE hire_date < '2020-01-01';

-- 插入时更新冲突
INSERT INTO employees (id, first_name, last_name, email, salary)
VALUES (1, 'John', 'Updated', 'john.updated@example.com', 80000.00)
ON CONFLICT (id) DO UPDATE SET
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    salary = EXCLUDED.salary,
    updated_at = CURRENT_TIMESTAMP;

-- 插入时忽略冲突
INSERT INTO employees (email, first_name, last_name)
VALUES ('existing@example.com', 'Test', 'User')
ON CONFLICT (email) DO NOTHING;
```

#### 3.3.2 更新数据

```sql
-- 简单更新
UPDATE employees 
SET salary = salary * 1.1 
WHERE department_id = 1;

-- 多列更新
UPDATE employees 
SET 
    salary = salary * 1.05,
    updated_at = CURRENT_TIMESTAMP
WHERE hire_date < CURRENT_DATE - INTERVAL '1 year';

-- 使用子查询更新
UPDATE employees 
SET department_id = (
    SELECT id FROM departments WHERE name = 'Engineering'
)
WHERE department_id IS NULL;

-- 更新并返回
UPDATE employees 
SET salary = salary * 1.1 
WHERE id = 1
RETURNING id, first_name, last_name, salary;

-- 条件更新（CASE）
UPDATE employees 
SET salary = CASE 
    WHEN department_id = 1 THEN salary * 1.15
    WHEN department_id = 2 THEN salary * 1.10
    ELSE salary * 1.05
END;
```

#### 3.3.3 删除数据

```sql
-- 删除特定行
DELETE FROM employees WHERE id = 100;

-- 删除多行
DELETE FROM employees WHERE department_id = 5;

-- 使用子查询删除
DELETE FROM employees 
WHERE department_id IN (
    SELECT id FROM departments WHERE name = 'Closed'
);

-- 删除并返回
DELETE FROM employees 
WHERE id = 100
RETURNING *;

-- 清空表（比 DELETE 更快，不可回滚）
TRUNCATE TABLE temp_data;
```

### 3.4 数据查询（DQL）

#### 3.4.1 基本查询

```sql
-- 选择所有列
SELECT * FROM employees;

-- 选择特定列
SELECT first_name, last_name, email FROM employees;

-- 去重
SELECT DISTINCT department_id FROM employees;

-- 限制结果数
SELECT * FROM employees LIMIT 10;
SELECT * FROM employees LIMIT 10 OFFSET 20;  -- 分页

-- 排序
SELECT * FROM employees ORDER BY salary DESC;
SELECT * FROM employees ORDER BY department_id ASC, salary DESC;

-- 条件过滤
SELECT * FROM employees WHERE salary > 50000;
SELECT * FROM employees WHERE department_id IN (1, 2, 3);
SELECT * FROM employees WHERE hire_date BETWEEN '2020-01-01' AND '2023-12-31';
SELECT * FROM employees WHERE email LIKE '%@example.com';
SELECT * FROM employees WHERE first_name ILIKE 'john%';  -- 不区分大小写
```

#### 3.4.2 聚合函数

```sql
-- 基本聚合
SELECT 
    COUNT(*) AS total_employees,
    COUNT(DISTINCT department_id) AS total_departments,
    AVG(salary) AS avg_salary,
    MAX(salary) AS max_salary,
    MIN(salary) AS min_salary,
    SUM(salary) AS total_salary
FROM employees;

-- 分组聚合
SELECT 
    department_id,
    COUNT(*) AS emp_count,
    AVG(salary) AS avg_salary,
    MAX(hire_date) AS latest_hire
FROM employees
GROUP BY department_id;

-- 分组过滤
SELECT 
    department_id,
    COUNT(*) AS emp_count,
    AVG(salary) AS avg_salary
FROM employees
GROUP BY department_id
HAVING COUNT(*) > 5 AND AVG(salary) > 60000;
```

#### 3.4.3 表连接

```sql
-- 内连接
SELECT e.first_name, e.last_name, d.name AS department
FROM employees e
INNER JOIN departments d ON e.department_id = d.id;

-- 左连接
SELECT e.first_name, e.last_name, d.name AS department
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id;

-- 右连接
SELECT e.first_name, e.last_name, d.name AS department
FROM employees e
RIGHT JOIN departments d ON e.department_id = d.id;

-- 全外连接
SELECT e.first_name, d.name
FROM employees e
FULL OUTER JOIN departments d ON e.department_id = d.id;

-- 交叉连接
SELECT e.first_name, p.project_name
FROM employees e
CROSS JOIN projects p;

-- 自连接
SELECT e1.first_name || ' ' || e1.last_name AS employee,
       e2.first_name || ' ' || e2.last_name AS manager
FROM employees e1
LEFT JOIN employees e2 ON e1.manager_id = e2.id;

-- 多表连接
SELECT 
    e.first_name,
    d.name AS department,
    p.name AS project
FROM employees e
JOIN departments d ON e.department_id = d.id
JOIN employee_projects ep ON e.id = ep.employee_id
JOIN projects p ON ep.project_id = p.id;
```

#### 3.4.4 子查询

```sql
-- 标量子查询
SELECT 
    first_name,
    last_name,
    (SELECT name FROM departments WHERE id = e.department_id) AS department
FROM employees e;

-- IN 子查询
SELECT * FROM employees 
WHERE department_id IN (
    SELECT id FROM departments WHERE location = 'New York'
);

-- EXISTS 子查询
SELECT * FROM departments d
WHERE EXISTS (
    SELECT 1 FROM employees WHERE department_id = d.id
);

-- 关联子查询
SELECT * FROM employees e
WHERE salary > (
    SELECT AVG(salary) FROM employees 
    WHERE department_id = e.department_id
);

-- CTE（公用表表达式）
WITH dept_avg AS (
    SELECT department_id, AVG(salary) AS avg_sal
    FROM employees
    GROUP BY department_id
)
SELECT e.*, d.avg_sal
FROM employees e
JOIN dept_avg d ON e.department_id = d.department_id
WHERE e.salary > d.avg_sal;
```

---

## 第4章 数据类型详解

### 4.1 数值类型

```sql
-- 整数类型
CREATE TABLE numeric_examples (
    -- 小整数 (-32768 到 32767)
    small_col SMALLINT,
    
    -- 标准整数 (-2147483648 到 2147483647)
    int_col INTEGER,
    
    -- 大整数 (-9223372036854775808 到 9223372036854775807)
    big_col BIGINT,
    
    -- 自增整数
    serial_col SERIAL,          -- 1 到 2147483647
    bigserial_col BIGSERIAL     -- 1 到 9223372036854775807
);

-- 精确数值
CREATE TABLE decimal_examples (
    -- NUMERIC(precision, scale)
    -- precision: 总位数, scale: 小数位数
    price NUMERIC(10, 2),       -- 最多 10 位，其中 2 位小数
    quantity NUMERIC(1000, 0),  -- 最多 1000 位整数
    exact_value NUMERIC         -- 无限制精度
);

-- 浮点数
CREATE TABLE float_examples (
    -- 单精度浮点数（约 6 位小数精度）
    real_col REAL,
    
    -- 双精度浮点数（约 15 位小数精度）
    double_col DOUBLE PRECISION
);

-- 使用示例
INSERT INTO decimal_examples (price, quantity)
VALUES (99999999.99, 12345678901234567890);
```

### 4.2 字符串类型

```sql
-- 字符串类型
CREATE TABLE string_examples (
    -- 定长字符串（不足补空格）
    fixed_char CHAR(10),
    
    -- 变长字符串（带长度限制）
    var_string VARCHAR(255),
    
    -- 变长字符串（无长度限制）
    text_col TEXT,
    
    -- 存储二进制数据
    bytea_col BYTEA
);

-- 字符串函数示例
SELECT 
    LENGTH('Hello World'),              -- 11
    UPPER('hello'),                      -- HELLO
    LOWER('WORLD'),                      -- world
    SUBSTRING('PostgreSQL' FROM 1 FOR 4), -- Post
    REPLACE('Hello World', 'World', 'PostgreSQL'),  -- Hello PostgreSQL
    CONCAT('Hello', ' ', 'World'),       -- Hello World
    'Hello' || ' ' || 'World',           -- Hello World (PostgreSQL 风格)
    TRIM('  Hello  '),                   -- Hello
    POSITION('SQL' IN 'PostgreSQL'),     -- 9
    SPLIT_PART('a,b,c,d', ',', 2);       -- b
```

### 4.3 日期和时间类型

```sql
-- 日期时间类型
CREATE TABLE datetime_examples (
    -- 日期（不含时间）
    date_col DATE,
    
    -- 时间（不含日期）
    time_col TIME,
    time_with_tz TIME WITH TIME ZONE,
    
    -- 日期和时间
    timestamp_col TIMESTAMP,
    timestamp_with_tz TIMESTAMP WITH TIME ZONE,
    
    -- 时间间隔
    interval_col INTERVAL
);

-- 日期时间函数
SELECT 
    CURRENT_DATE,                       -- 当前日期
    CURRENT_TIME,                       -- 当前时间
    CURRENT_TIMESTAMP,                  -- 当前日期时间
    NOW(),                              -- 当前日期时间
    
    -- 日期运算
    CURRENT_DATE + INTERVAL '1 day',    -- 明天
    CURRENT_DATE - INTERVAL '1 month',  -- 上月今天
    DATE_TRUNC('month', CURRENT_DATE),  -- 月初
    
    -- 提取部分
    EXTRACT(YEAR FROM CURRENT_DATE),    -- 年份
    EXTRACT(MONTH FROM CURRENT_DATE),   -- 月份
    EXTRACT(DAY FROM CURRENT_DATE),     -- 日期
    EXTRACT(DOW FROM CURRENT_DATE),     -- 星期几 (0=周日)
    
    -- 格式化
    TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD'),           -- 2024-01-15
    TO_CHAR(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS'),  -- 2024-01-15 14:30:00
    
    -- 解析
    TO_DATE('2024-01-15', 'YYYY-MM-DD'),
    TO_TIMESTAMP('2024-01-15 14:30:00', 'YYYY-MM-DD HH24:MI:SS'),
    
    -- 年龄计算
    AGE('1990-05-15'::DATE),            -- 从出生到现在的年龄
    AGE('2020-01-01'::DATE, '1990-05-15'::DATE);  -- 两个日期之间的年龄

-- 时区处理
SET TIME ZONE 'Asia/Shanghai';
SELECT CURRENT_TIMESTAMP AT TIME ZONE 'UTC';
SELECT CURRENT_TIMESTAMP AT TIME ZONE 'America/New_York';
```

### 4.4 布尔类型

```sql
-- 布尔类型
CREATE TABLE boolean_examples (
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    has_permission BOOLEAN
);

-- 布尔值
INSERT INTO boolean_examples VALUES (TRUE, FALSE, NULL);
INSERT INTO boolean_examples VALUES ('yes', 'no', '1');  -- 字符串也可以
INSERT INTO boolean_examples VALUES (1, 0, NULL);        -- 整数也可以

-- 有效值: TRUE, 't', 'true', 'y', 'yes', 'on', '1'
-- 有效值: FALSE, 'f', 'false', 'n', 'no', 'off', '0'
```

### 4.5 JSON 和 JSONB 类型

```sql
-- JSON 类型
CREATE TABLE json_examples (
    id SERIAL PRIMARY KEY,
    -- JSON: 存储原始文本，解析时验证
    data_json JSON,
    -- JSONB: 二进制存储，支持索引，处理更快
    data_jsonb JSONB
);

-- 插入 JSON 数据
INSERT INTO json_examples (data_json, data_jsonb) VALUES (
    '{"name": "John", "age": 30, "skills": ["SQL", "Python"]}',
    '{"name": "John", "age": 30, "skills": ["SQL", "Python"]}'
);

-- JSON 操作符
SELECT 
    -- 获取 JSON 字段
    data_jsonb -> 'name',           -- "John" (JSON)
    data_jsonb ->> 'name',          -- John (文本)
    
    -- 获取嵌套字段
    data_jsonb #> '{skills, 0}',    -- "SQL"
    
    -- 包含检查
    data_jsonb @> '{"age": 30}',    -- true
    '{"age": 30}' <@ data_jsonb,    -- true
    
    -- 键存在检查
    data_jsonb ? 'name',            -- true
    data_jsonb ?| ARRAY['name', 'email'],  -- true（任一存在）
    data_jsonb ?& ARRAY['name', 'age'],    -- true（全部存在）
    
    -- 更新 JSON
    jsonb_set(data_jsonb, '{age}', '31'),
    data_jsonb || '{"city": "Beijing"}'::jsonb,
    
    -- 删除键
    data_jsonb - 'age',
    data_jsonb #- '{skills, 0}';

-- JSON 函数
SELECT 
    jsonb_pretty(data_jsonb),       -- 格式化输出
    jsonb_each(data_jsonb),         -- 展开为键值对
    jsonb_each_text(data_jsonb),    -- 展开为文本键值对
    jsonb_array_elements('[1,2,3]'::jsonb),  -- 展开数组
    jsonb_object_keys(data_jsonb);  -- 获取所有键

-- JSON 索引
CREATE INDEX idx_jsonb_name ON json_examples USING GIN ((data_jsonb -> 'name'));
CREATE INDEX idx_jsonb_data ON json_examples USING GIN (data_jsonb);
```


### 5.1 JSON/JSONB使用

JSON和JSONB是PostgreSQL处理半结构化数据的核心类型，广泛应用于现代Web应用。

**JSON vs JSONB对比**

| 特性 | JSON | JSONB |
|------|------|-------|
| 存储格式 | 原始文本 | 二进制分解 |
| 存储空间 | 较大 | 较小（去除空白） |
| 写入性能 | 较快 | 较慢（需要解析） |
| 查询性能 | 较慢 | 较快 |
| 索引支持 | 不支持 | 支持GIN索引 |
| 键顺序 | 保留 | 不保留 |
| 重复键 | 保留 | 去重（保留最后一个） |

**JSONB操作详解**

```sql
-- 创建示例表
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    attributes JSONB,
    specs JSONB
);

-- 插入数据
INSERT INTO products (name, attributes, specs) VALUES
('iPhone 15', 
 '{"brand": "Apple", "category": "phone", "price": 799, "in_stock": true}',
 '{"screen": "6.1 inch", "storage": ["128GB", "256GB", "512GB"], "colors": ["black", "blue", "pink"]}'
),
('MacBook Pro', 
 '{"brand": "Apple", "category": "laptop", "price": 1999, "in_stock": true}',
 '{"screen": "14 inch", "cpu": "M3 Pro", "ram": ["16GB", "32GB"]}'
),
('Samsung S24', 
 '{"brand": "Samsung", "category": "phone", "price": 899, "in_stock": false}',
 '{"screen": "6.2 inch", "storage": ["256GB", "512GB"], "colors": ["gray", "purple"]}'
);

-- 基本查询操作符
SELECT name, attributes->>'brand' as brand FROM products;  -- 提取文本
SELECT name, attributes->'price' as price FROM products;   -- 提取JSON
SELECT name, specs->'storage'->>0 as base_storage FROM products;  -- 嵌套提取

-- 包含操作符 @>
SELECT * FROM products WHERE attributes @> '{"brand": "Apple"}';
SELECT * FROM products WHERE specs @> '{"storage": ["128GB"]}';

-- 被包含操作符 <@
SELECT * FROM products WHERE '"phone"' <@ attributes->'category';

-- 键存在操作符 ?
SELECT * FROM products WHERE attributes ? 'price';
SELECT * FROM products WHERE specs->'colors' ? 'black';

-- 任意键存在 ?|
SELECT * FROM products WHERE attributes ?| ARRAY['brand', 'manufacturer'];

-- 所有键存在 ?&
SELECT * FROM products WHERE attributes ?& ARRAY['brand', 'price'];

-- 路径提取 #>
SELECT specs#>'{storage,0}' FROM products;  -- 获取storage数组第一个元素
```

**JSONB函数**

```sql
-- jsonb_each - 展开为键值对
SELECT * FROM jsonb_each('{"a": 1, "b": 2}'::jsonb);

-- jsonb_each_text - 展开为文本键值对
SELECT * FROM jsonb_each_text('{"a": 1, "b": 2}'::jsonb);

-- jsonb_extract_path - 路径提取
SELECT jsonb_extract_path(attributes, 'brand') FROM products;

-- jsonb_array_elements - 展开数组
SELECT jsonb_array_elements(specs->'storage') FROM products WHERE id = 1;

-- jsonb_array_length - 数组长度
SELECT jsonb_array_length(specs->'storage') FROM products;

-- jsonb_typeof - 获取JSON类型
SELECT jsonb_typeof(attributes->'price') FROM products;

-- jsonb_pretty - 格式化输出
SELECT jsonb_pretty(attributes) FROM products WHERE id = 1;

-- jsonb_set - 更新JSON值
UPDATE products 
SET attributes = jsonb_set(attributes, '{price}', '699')
WHERE id = 1;

-- jsonb_insert - 插入数组元素
UPDATE products 
SET specs = jsonb_insert(specs, '{storage,0}', '"64GB"')
WHERE id = 1;

-- jsonb_delete - 删除键
UPDATE products 
SET attributes = attributes - 'in_stock'
WHERE id = 1;

-- 删除数组元素
UPDATE products 
SET specs = specs #- '{colors,0}'
WHERE id = 1;
```

**JSONB索引**

```sql
-- GIN索引（推荐）
CREATE INDEX idx_products_attributes ON products USING GIN (attributes);
CREATE INDEX idx_products_specs ON products USING GIN (specs);

-- 特定路径的GIN索引
CREATE INDEX idx_products_brand ON products USING GIN ((attributes->'brand'));

-- B-tree索引（用于等值查询）
CREATE INDEX idx_products_price ON products USING BTREE ((attributes->>'price'));
```

**实际应用场景**

```sql
-- 电商产品属性存储
CREATE TABLE ecommerce_products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    base_price NUMERIC(10,2) NOT NULL,
    -- 动态属性（不同品类有不同属性）
    attributes JSONB NOT NULL DEFAULT '{}',
    -- 变体信息（颜色、尺寸等）
    variants JSONB DEFAULT '[]',
    -- 多语言描述
    translations JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入不同品类的产品
INSERT INTO ecommerce_products (sku, name, base_price, attributes, variants, translations) VALUES
-- 服装
('TSHIRT-001', 'Cotton T-Shirt', 29.99,
 '{"material": "cotton", "fit": "regular", "care": "machine wash"}',
 '[{"color": "black", "size": "M", "stock": 100}, {"color": "white", "size": "L", "stock": 50}]',
 '{"en": {"desc": "Comfortable cotton tee"}, "zh": {"desc": "舒适棉质T恤"}}'
),
-- 电子产品
('PHONE-001', 'Smartphone', 599.99,
 '{"screen_size": "6.5 inch", "battery": "5000mAh", "os": "Android 14"}',
 '[{"color": "blue", "storage": "128GB", "stock": 200}]',
 '{"en": {"desc": "Latest smartphone"}, "zh": {"desc": "最新智能手机"}}'
);

-- 查询特定属性的产品
SELECT * FROM ecommerce_products 
WHERE attributes @> '{"material": "cotton"}';

-- 查询有库存的变体
SELECT * FROM ecommerce_products 
WHERE variants @> '[{"stock": {"gt": 0}}]';
```


### 4.6 数组类型

```sql
-- 数组类型
CREATE TABLE array_examples (
    id SERIAL PRIMARY KEY,
    tags TEXT[],
    scores INTEGER[],
    matrix INTEGER[][],
    schedule TIMESTAMP[]
);

-- 插入数组数据
INSERT INTO array_examples (tags, scores, matrix) VALUES (
    ARRAY['database', 'sql', 'postgresql'],
    ARRAY[85, 90, 78, 92],
    ARRAY[ARRAY[1, 2, 3], ARRAY[4, 5, 6], ARRAY[7, 8, 9]]
);

-- 数组操作
SELECT 
    -- 访问元素
    tags[1],                    -- database (PostgreSQL 数组从 1 开始)
    scores[2:4],                -- 切片 {90,78,92}
    
    -- 数组函数
    array_length(tags, 1),      -- 数组长度
    array_dims(matrix),         -- 数组维度
    array_ndims(matrix),        -- 维度数
    cardinality(scores),        -- 元素总数
    
    -- 数组操作
    tags || ARRAY['new_tag'],   -- 追加元素
    array_append(tags, 'new_tag'),
    array_prepend('first_tag', tags),
    array_cat(tags, ARRAY['a', 'b']),
    
    -- 包含检查
    tags @> ARRAY['sql'],       -- 包含
    ARRAY['sql'] <@ tags,       -- 被包含
    'sql' = ANY(tags),          -- 任一元素等于
    'java' != ALL(tags),        -- 所有元素不等于
    
    -- 去重和排序
    ARRAY(SELECT DISTINCT UNNEST(tags)),
    ARRAY(SELECT UNNEST(tags) ORDER BY 1);

-- 展开数组
SELECT id, UNNEST(tags) AS tag FROM array_examples;

-- 数组聚合
SELECT department_id, ARRAY_AGG(name) AS employees
FROM employees
GROUP BY department_id;
```


### 5.2 数组操作

PostgreSQL的数组类型支持多维数组和丰富的操作符。

**数组定义与操作**

```sql
-- 创建数组列
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    scores INTEGER[],              -- 一维数组
    schedule TEXT[][]              -- 二维数组（课程表）
);

-- 插入数组数据
INSERT INTO students (name, scores, schedule) VALUES
('Alice', ARRAY[85, 90, 78, 92], 
 ARRAY[
   ARRAY['Math', 'English'],
   ARRAY['Physics', 'Chemistry'],
   ARRAY['History', 'Geography']
 ]
),
('Bob', ARRAY[75, 88, 92, 85], 
 ARRAY[
   ARRAY['Biology', 'Math'],
   ARRAY['English', 'Art'],
   ARRAY['Music', 'PE']
 ]
);

-- 数组访问
SELECT scores[1] FROM students;           -- 第一个元素（PostgreSQL数组从1开始）
SELECT scores[1:3] FROM students;         -- 切片
SELECT schedule[1][2] FROM students;      -- 二维数组访问

-- 数组操作符
SELECT * FROM students WHERE scores @> ARRAY[90];      -- 包含90
SELECT * FROM students WHERE scores && ARRAY[85, 90];  -- 有交集
SELECT * FROM students WHERE scores = ARRAY[85, 90, 78, 92];  -- 相等
SELECT * FROM students WHERE scores <@ ARRAY[70, 75, 78, 80, 85, 88, 90, 92];  -- 被包含

-- 数组连接
SELECT ARRAY[1,2] || ARRAY[3,4];          -- {1,2,3,4}
SELECT ARRAY[1,2] || 3;                   -- {1,2,3}
```

**数组函数**

```sql
-- array_length - 数组维度长度
SELECT array_length(scores, 1) FROM students;

-- array_dims - 数组维度信息
SELECT array_dims(schedule) FROM students;

-- array_lower / array_upper - 边界
SELECT array_lower(scores, 1), array_upper(scores, 1) FROM students;

-- unnest - 展开数组
SELECT name, unnest(scores) as score FROM students;

-- array_agg - 聚合为数组
SELECT array_agg(name) FROM students;

-- string_to_array / array_to_string
SELECT string_to_array('a,b,c', ',');     -- {a,b,c}
SELECT array_to_string(ARRAY[1,2,3], '-'); -- 1-2-3

-- array_position - 查找位置
SELECT array_position(ARRAY['a','b','c'], 'b');  -- 2

-- array_remove - 移除元素
SELECT array_remove(ARRAY[1,2,3,2], 2);   -- {1,3}

-- array_replace - 替换元素
SELECT array_replace(ARRAY[1,2,3,2], 2, 9);  -- {1,9,3,9}

-- cardinality - 元素总数
SELECT cardinality(ARRAY[1,2,3]);         -- 3
```

**数组与GIN索引**

```sql
-- 创建GIN索引加速数组查询
CREATE INDEX idx_students_scores ON students USING GIN (scores);

-- 查询使用索引
EXPLAIN SELECT * FROM students WHERE scores @> ARRAY[90];
```


### 4.7 范围类型

```sql
-- 范围类型
CREATE TABLE range_examples (
    id SERIAL PRIMARY KEY,
    -- 整数范围
    int_range INT4RANGE,
    -- 大整数范围
    bigint_range INT8RANGE,
    -- 数值范围
    num_range NUMRANGE,
    -- 时间戳范围
    ts_range TSRANGE,
    -- 带时区的时间戳范围
    tstz_range TSTZRANGE,
    -- 日期范围
    date_range DATERANGE
);

-- 插入范围数据
INSERT INTO range_examples (int_range, ts_range, date_range) VALUES (
    '[1, 10)',                          -- 包含 1，不包含 10
    '["2024-01-01 00:00:00", "2024-01-31 23:59:59")',
    '[2024-01-01, 2024-01-31]'
);

-- 范围操作
SELECT 
    -- 范围边界
    LOWER(int_range),           -- 下界
    UPPER(int_range),           -- 上界
    ISEMPTY(int_range),         -- 是否为空
    LOWER_INC(int_range),       -- 下界是否包含
    UPPER_INC(int_range),       -- 上界是否包含
    
    -- 范围运算
    int_range @> 5,             -- 包含值
    int_range @> '[2, 5)'::int4range,  -- 包含范围
    int_range && '[5, 15)'::int4range,  -- 有重叠
    int_range << '[20, 30)'::int4range, -- 严格在左边
    int_range >> '[-10, 0)'::int4range, -- 严格在右边
    
    -- 范围合并和交集
    int_range + '[10, 20)'::int4range,  -- 并集
    int_range * '[5, 15)'::int4range,   -- 交集
    int_range - '[5, 8)'::int4range;    -- 差集
```


### 5.3 范围类型

范围类型表示一个值的范围，支持多种内置范围类型。

**内置范围类型**

```sql
INT4RANGE    -- 整数范围
INT8RANGE    -- 大整数范围
NUMRANGE     -- 数值范围
TSRANGE      -- 无时区时间戳范围
TSTZRANGE    -- 带时区时间戳范围
DATERANGE    -- 日期范围
```

**范围类型操作**

```sql
-- 创建表
CREATE TABLE reservations (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL,
    guest_name VARCHAR(100),
    stay_period DATERANGE NOT NULL,
    price_range NUMRANGE
);

-- 插入数据（使用范围构造器）
INSERT INTO reservations (room_id, guest_name, stay_period, price_range) VALUES
(101, 'John Doe', '[2024-01-01, 2024-01-05)', '[100.00, 150.00)'),
(102, 'Jane Smith', '[2024-01-03, 2024-01-07)', '[120.00, 180.00)'),
(101, 'Bob Wilson', '[2024-01-10, 2024-01-15)', '[90.00, 130.00)');

-- 范围构造方式
SELECT '[1, 10]'::int4range;     -- 包含1和10
SELECT '[1, 10)'::int4range;     -- 包含1，不包含10
SELECT '(1, 10]'::int4range;     -- 不包含1，包含10
SELECT '(1, 10)'::int4range;     -- 不包含1和10
SELECT int4range(1, 10, '[]');   -- 使用函数构造

-- 范围操作符
SELECT * FROM reservations WHERE stay_period @> '2024-01-02'::date;  -- 包含日期
SELECT * FROM reservations WHERE stay_period && '[2024-01-04, 2024-01-06)'::daterange;  -- 重叠
SELECT * FROM reservations WHERE stay_period << '[2024-01-20, 2024-01-25)'::daterange;  -- 严格在左
SELECT * FROM reservations WHERE stay_period >> '[2023-12-01, 2023-12-31)'::daterange;  -- 严格在右

-- 范围函数
SELECT lower(stay_period), upper(stay_period) FROM reservations;  -- 边界值
SELECT lower_inc(stay_period), upper_inc(stay_period) FROM reservations;  -- 边界包含性
SELECT isempty('[1,1)'::int4range);  -- 是否为空
```

**排除约束（防止重叠）**

```sql
-- 确保同一房间不会有重叠的预订
ALTER TABLE reservations 
ADD CONSTRAINT no_overlapping_reservations 
EXCLUDE USING GIST (room_id WITH =, stay_period WITH &&);

-- 测试：尝试插入重叠预订会失败
INSERT INTO reservations (room_id, guest_name, stay_period) 
VALUES (101, 'Conflict', '[2024-01-02, 2024-01-04)');
-- ERROR:  conflicting key value violates exclusion constraint
```


### 4.8 几何类型

```sql
-- 几何类型
CREATE TABLE geometry_examples (
    id SERIAL PRIMARY KEY,
    point_col POINT,            -- 点
    line_col LINE,              -- 无限直线
    lseg_col LSEG,              -- 线段
    box_col BOX,                -- 矩形
    path_col PATH,              -- 路径（开放或闭合）
    polygon_col POLYGON,        -- 多边形
    circle_col CIRCLE           -- 圆
);

-- 插入几何数据
INSERT INTO geometry_examples VALUES (
    POINT(1, 2),
    LINE(POINT(0, 0), POINT(1, 1)),
    LSEG(POINT(0, 0), POINT(3, 4)),
    BOX(POINT(0, 0), POINT(2, 2)),
    PATH('((0,0),(1,1),(2,0))'),
    POLYGON('((0,0),(1,1),(2,0))'),
    CIRCLE(POINT(0, 0), 5)
);

-- 几何操作
SELECT 
    -- 距离
    POINT(0, 0) <-> POINT(3, 4),    -- 5 (欧几里得距离)
    
    -- 包含
    CIRCLE(POINT(0, 0), 5) @> POINT(3, 4),  -- true
    
    -- 相交
    BOX(POINT(0, 0), POINT(2, 2)) && BOX(POINT(1, 1), POINT(3, 3)),  -- true
    
    -- 面积
    AREA(POLYGON('((0,0),(4,0),(4,3))'));   -- 6
```

### 4.9 UUID 类型

```sql
-- 启用 UUID 扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 使用 UUID
CREATE TABLE uuid_examples (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100)
);

-- UUID 生成函数
SELECT 
    uuid_generate_v4(),         -- 随机 UUID (版本 4)
    uuid_generate_v1(),         -- 基于时间的 UUID (版本 1)
    uuid_nil(),                 -- 空 UUID
    uuid_ns_dns(),              -- DNS 命名空间 UUID
    uuid_ns_url();              -- URL 命名空间 UUID
```

### 4.10 枚举类型

```sql
-- 创建枚举类型
CREATE TYPE status_enum AS ENUM ('pending', 'processing', 'completed', 'cancelled');
CREATE TYPE priority_enum AS ENUM ('low', 'medium', 'high', 'urgent');

-- 使用枚举类型
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    status status_enum DEFAULT 'pending',
    priority priority_enum DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 枚举操作
SELECT 
    ENUM_FIRST(NULL::status_enum),      -- pending
    ENUM_LAST(NULL::status_enum),       -- cancelled
    ENUM_RANGE(NULL::status_enum);      -- {pending,processing,completed,cancelled}

-- 添加枚举值
ALTER TYPE status_enum ADD VALUE 'on_hold' AFTER 'processing';
```

---

## 第5章 索引与优化

### 5.1 索引基础

```sql
-- 创建索引
CREATE INDEX idx_employees_name ON employees(last_name);
CREATE INDEX idx_employees_email ON employees(email);

-- 唯一索引
CREATE UNIQUE INDEX idx_employees_unique_email ON employees(email);

-- 复合索引
CREATE INDEX idx_employees_dept_salary ON employees(department_id, salary);

-- 部分索引（条件索引）
CREATE INDEX idx_active_employees ON employees(last_name) 
WHERE is_active = TRUE;

-- 函数索引
CREATE INDEX idx_employees_lower_email ON employees(LOWER(email));

-- 表达式索引
CREATE INDEX idx_employees_fullname ON employees 
    ((first_name || ' ' || last_name));

-- 删除索引
DROP INDEX IF EXISTS idx_employees_name;

-- 查看表上的索引
\di employees
SELECT * FROM pg_indexes WHERE tablename = 'employees';

-- 分析索引使用情况
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,           -- 索引扫描次数
    idx_tup_read,       -- 通过索引读取的元组数
    idx_tup_fetch       -- 通过索引获取的活跃元组数
FROM pg_stat_user_indexes
WHERE tablename = 'employees';
```

### 5.2 B-tree 索引

B-tree 是 PostgreSQL 默认的索引类型，适用于等值和范围查询。

```sql
-- B-tree 索引（默认）
CREATE INDEX idx_employees_salary ON employees USING BTREE(salary);

-- 适用于以下查询
SELECT * FROM employees WHERE salary = 50000;           -- 等值查询
SELECT * FROM employees WHERE salary > 50000;           -- 范围查询
SELECT * FROM employees WHERE salary BETWEEN 40000 AND 60000;
SELECT * FROM employees ORDER BY salary LIMIT 10;       -- 排序
SELECT * FROM employees WHERE last_name LIKE 'Sm%';     -- 前缀匹配

-- 多列 B-tree 索引
CREATE INDEX idx_employees_name ON employees 
    USING BTREE(last_name, first_name);

-- 索引只扫描（Index Only Scan）
CREATE INDEX idx_employees_covering ON employees 
    (department_id) INCLUDE (first_name, last_name, salary);
```

### 5.3 Hash 索引

Hash 索引适用于等值查询，在 PostgreSQL 10+ 中已支持 WAL 日志和复制。

```sql
-- Hash 索引
CREATE INDEX idx_employees_hash_email ON employees USING HASH(email);

-- 仅适用于等值查询
SELECT * FROM employees WHERE email = 'john@example.com';

-- 不适用于范围查询（不会使用索引）
SELECT * FROM employees WHERE email > 'a';  -- 不会使用 hash 索引
```

### 5.4 GiST 索引

GiST（Generalized Search Tree）是一种可扩展的索引框架，支持多种数据类型。

```sql
-- GiST 索引用于几何类型
CREATE INDEX idx_locations_point ON locations USING GIST(point_col);

-- GiST 索引用于范围类型
CREATE INDEX idx_reservations_during ON reservations USING GIST(during);

-- 范围查询示例
SELECT * FROM reservations 
WHERE during && '["2024-01-15 10:00", "2024-01-15 12:00")'::tsrange;

-- 最近邻搜索
SELECT * FROM locations 
ORDER BY point_col <-> POINT(0, 0) 
LIMIT 5;
```

### 5.5 GIN 索引

GIN（Generalized Inverted Index）适用于包含多个值的列，如数组、JSONB、全文搜索。

```sql
-- GIN 索引用于数组
CREATE INDEX idx_array_tags ON array_examples USING GIN(tags);

-- 数组包含查询
SELECT * FROM array_examples WHERE tags @> ARRAY['sql'];

-- GIN 索引用于 JSONB
CREATE INDEX idx_jsonb_data ON json_examples USING GIN(data_jsonb);

-- JSONB 包含查询
SELECT * FROM json_examples WHERE data_jsonb @> '{"age": 30}';

-- GIN 索引用于全文搜索
CREATE INDEX idx_articles_content ON articles 
    USING GIN(to_tsvector('english', content));

-- 全文搜索查询
SELECT * FROM articles 
WHERE to_tsvector('english', content) @@ to_tsquery('english', 'database & postgresql');
```

### 5.6 BRIN 索引

BRIN（Block Range Index）适用于大型、自然有序的表，索引体积小。

```sql
-- BRIN 索引（适合时间序列数据）
CREATE INDEX idx_logs_timestamp ON logs 
    USING BRIN(created_at) 
    WITH (pages_per_range = 128);

-- 适用于范围查询
SELECT * FROM logs 
WHERE created_at BETWEEN '2024-01-01' AND '2024-01-31';
```

### 5.7 SP-GiST 索引

SP-GiST（Space-Partitioned GiST）适用于空间分区数据结构。

```sql
-- SP-GiST 索引
CREATE INDEX idx_quad_point ON locations USING SPGIST(point_col);

-- 适用于四叉树、kd 树等空间分区查询
```

### 5.8 索引优化技巧

```sql
-- 1. 选择合适的索引类型
-- 等值查询: B-tree, Hash
-- 范围查询: B-tree, BRIN
-- 数组/JSONB: GIN
-- 几何/范围: GiST
-- 全文搜索: GIN

-- 2. 使用覆盖索引减少回表
CREATE INDEX idx_covering ON orders 
    (customer_id, order_date) 
    INCLUDE (total_amount, status);

-- 3. 部分索引减少索引大小
CREATE INDEX idx_recent_orders ON orders(order_date) 
WHERE order_date > '2023-01-01';

-- 4. 多列索引列顺序
-- 等值过滤列在前，范围过滤列在后
CREATE INDEX idx_good ON orders 
    (status, customer_id, order_date);

-- 5. 定期维护索引
-- 分析表
ANALYZE employees;

-- 重建索引
REINDEX INDEX idx_employees_name;
REINDEX TABLE employees;

-- 清理索引膨胀
VACUUM ANALYZE employees;

-- 6. 查看查询计划
EXPLAIN ANALYZE 
SELECT * FROM employees 
WHERE department_id = 1 AND salary > 50000;

-- 7. 索引使用统计
SELECT 
    relname AS table_name,
    indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

---

## 第6章 高级特性

### 6.1 分区表

分区表将大表分成更小、更易管理的部分。

```sql
-- 创建范围分区表
CREATE TABLE measurements (
    logdate DATE NOT NULL,
    peaktemp INT,
    unitsales INT
) PARTITION BY RANGE (logdate);

-- 创建分区
CREATE TABLE measurements_y2024m01 PARTITION OF measurements
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE measurements_y2024m02 PARTITION OF measurements
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

CREATE TABLE measurements_y2024m03 PARTITION OF measurements
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');

-- 默认分区（存储不匹配任何分区的数据）
CREATE TABLE measurements_default PARTITION OF measurements DEFAULT;

-- 列表分区
CREATE TABLE regions (
    region_id INT,
    country VARCHAR(100),
    sales INT
) PARTITION BY LIST (country);

CREATE TABLE regions_asia PARTITION OF regions
    FOR VALUES IN ('China', 'Japan', 'India', 'Korea');

CREATE TABLE regions_europe PARTITION OF regions
    FOR VALUES IN ('Germany', 'France', 'UK', 'Italy');

CREATE TABLE regions_americas PARTITION OF regions
    FOR VALUES IN ('USA', 'Canada', 'Brazil', 'Mexico');

-- 哈希分区
CREATE TABLE orders_hash (
    order_id BIGINT,
    customer_id INT,
    order_date DATE,
    amount NUMERIC
) PARTITION BY HASH (customer_id);

CREATE TABLE orders_hash_p0 PARTITION OF orders_hash
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);

CREATE TABLE orders_hash_p1 PARTITION OF orders_hash
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);

CREATE TABLE orders_hash_p2 PARTITION OF orders_hash
    FOR VALUES WITH (MODULUS 4, REMAINDER 2);

CREATE TABLE orders_hash_p3 PARTITION OF orders_hash
    FOR VALUES WITH (MODULUS 4, REMAINDER 3);

-- 子分区（组合分区）
CREATE TABLE sales (
    sale_id INT,
    sale_date DATE,
    region VARCHAR(50),
    amount NUMERIC
) PARTITION BY RANGE (sale_date);

CREATE TABLE sales_q1_2024 PARTITION OF sales
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01')
    PARTITION BY LIST (region);

CREATE TABLE sales_q1_2024_north PARTITION OF sales_q1_2024
    FOR VALUES IN ('North');

CREATE TABLE sales_q1_2024_south PARTITION OF sales_q1_2024
    FOR VALUES IN ('South');

-- 分区维护
-- 添加新分区
CREATE TABLE measurements_y2024m04 PARTITION OF measurements
    FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');

-- 分离分区
ALTER TABLE measurements DETACH PARTITION measurements_y2024m01;

-- 附加分区
ALTER TABLE measurements ATTACH PARTITION measurements_y2024m01
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- 删除分区
DROP TABLE measurements_y2024m01;

-- 分区查询优化
-- 查询会自动只扫描相关分区
EXPLAIN ANALYZE 
SELECT * FROM measurements 
WHERE logdate BETWEEN '2024-01-15' AND '2024-01-20';

-- 查看分区信息
SELECT 
    parent.relname AS parent_table,
    child.relname AS partition_name,
    pg_get_expr(child.relpartbound, child.oid) AS partition_bounds
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child ON pg_inherits.inhrelid = child.oid
WHERE parent.relname = 'measurements';
```

### 6.2 并行查询

PostgreSQL 支持并行执行查询以利用多核 CPU。

```sql
-- 启用并行查询（默认启用）
SET max_parallel_workers_per_gather = 4;
SET parallel_tuple_cost = 0.1;
SET parallel_setup_cost = 1000;

-- 查看并行查询计划
EXPLAIN (ANALYZE, VERBOSE, BUFFERS)
SELECT COUNT(*) FROM large_table;

-- 强制启用/禁用并行
SET max_parallel_workers_per_gather = 0;  -- 禁用
SET max_parallel_workers_per_gather = 8;  -- 启用最多 8 个 worker

-- 表级并行设置
ALTER TABLE large_table SET (parallel_workers = 4);

-- 并行查询示例
EXPLAIN (ANALYZE, COSTS OFF)
SELECT COUNT(*) FROM orders WHERE amount > 1000;

-- 输出示例：
-- Finalize Aggregate
--   ->  Gather
--         Workers Planned: 4
--         Workers Launched: 4
--         ->  Partial Aggregate
--               ->  Parallel Seq Scan on orders

-- 支持并行的操作
-- - 顺序扫描
-- - 索引扫描（B-tree）
-- - 位图堆扫描
-- - 嵌套循环连接
-- - 哈希连接
-- - 合并连接
-- - 聚合（COUNT, SUM, AVG 等）
```

### 6.3 公共表表达式（CTE）

CTE 提供了一种编写复杂查询的方式，使 SQL 更具可读性。

```sql
-- 基本 CTE
WITH high_earners AS (
    SELECT * FROM employees WHERE salary > 80000
)
SELECT * FROM high_earners WHERE department_id = 1;

-- 多个 CTE
WITH 
    dept_stats AS (
        SELECT 
            department_id,
            COUNT(*) AS emp_count,
            AVG(salary) AS avg_salary
        FROM employees
        GROUP BY department_id
    ),
    high_avg_depts AS (
        SELECT department_id FROM dept_stats WHERE avg_salary > 70000
    )
SELECT e.*
FROM employees e
WHERE e.department_id IN (SELECT department_id FROM high_avg_depts);

-- 递归 CTE（处理层次数据）
WITH RECURSIVE subordinates AS (
    -- 基础查询：找到起始员工
    SELECT id, first_name, last_name, manager_id, 0 AS level
    FROM employees
    WHERE id = 1  -- CEO
    
    UNION ALL
    
    -- 递归查询：找到下属
    SELECT e.id, e.first_name, e.last_name, e.manager_id, s.level + 1
    FROM employees e
    INNER JOIN subordinates s ON e.manager_id = s.id
)
SELECT * FROM subordinates ORDER BY level, last_name;

-- 递归 CTE（生成序列）
WITH RECURSIVE numbers AS (
    SELECT 1 AS n
    UNION ALL
    SELECT n + 1 FROM numbers WHERE n < 100
)
SELECT * FROM numbers;

-- 递归 CTE（路径遍历）
WITH RECURSIVE org_path AS (
    SELECT 
        id, 
        name, 
        parent_id,
        name AS path
    FROM departments
    WHERE parent_id IS NULL
    
    UNION ALL
    
    SELECT 
        d.id, 
        d.name, 
        d.parent_id,
        op.path || ' > ' || d.name
    FROM departments d
    JOIN org_path op ON d.parent_id = op.id
)
SELECT * FROM org_path ORDER BY path;

-- 物化 CTE（PostgreSQL 12+）
WITH cte_name AS MATERIALIZED (
    SELECT * FROM large_table WHERE complex_condition
)
SELECT * FROM cte_name WHERE ...;

-- 非物化 CTE（内联优化）
WITH cte_name AS NOT MATERIALIZED (
    SELECT * FROM large_table WHERE condition
)
SELECT * FROM cte_name WHERE ...;
```

### 6.4 窗口函数

窗口函数对一组行执行计算，类似于聚合函数，但不会将行分组。

```sql
-- 基本窗口函数
SELECT 
    id,
    first_name,
    last_name,
    department_id,
    salary,
    
    -- 行号
    ROW_NUMBER() OVER (ORDER BY salary DESC) AS row_num,
    
    -- 排名（相同值排名相同，会跳过排名）
    RANK() OVER (ORDER BY salary DESC) AS rank_num,
    
    -- 密集排名（相同值排名相同，不跳过排名）
    DENSE_RANK() OVER (ORDER BY salary DESC) AS dense_rank_num,
    
    -- 百分比排名
    PERCENT_RANK() OVER (ORDER BY salary DESC) AS pct_rank,
    
    -- 分桶（ntile）
    NTILE(4) OVER (ORDER BY salary DESC) AS quartile
FROM employees;

-- 分区窗口函数
SELECT 
    id,
    first_name,
    department_id,
    salary,
    
    -- 部门内排名
    RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) AS dept_rank,
    
    -- 部门内累计和
    SUM(salary) OVER (PARTITION BY department_id ORDER BY salary) AS running_total,
    
    -- 部门平均工资
    AVG(salary) OVER (PARTITION BY department_id) AS dept_avg,
    
    -- 与部门平均的差值
    salary - AVG(salary) OVER (PARTITION BY department_id) AS diff_from_avg
FROM employees;

-- 窗口帧（Window Frame）
SELECT 
    order_date,
    amount,
    
    -- 当前行及之前所有行
    SUM(amount) OVER (
        ORDER BY order_date 
        ROWS UNBOUNDED PRECEDING
    ) AS cumulative_sum,
    
    -- 当前行及之前 2 行
    AVG(amount) OVER (
        ORDER BY order_date 
        ROWS 2 PRECEDING
    ) AS moving_avg_3d,
    
    -- 当前行前后各 1 行
    AVG(amount) OVER (
        ORDER BY order_date 
        ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING
    ) AS centered_avg,
    
    -- 范围帧（相同值视为一组）
    SUM(amount) OVER (
        ORDER BY order_date 
        RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
    ) AS week_sum
FROM daily_sales;

-- 取值窗口函数
SELECT 
    id,
    salary,
    
    -- 第一行值
    FIRST_VALUE(salary) OVER (ORDER BY salary) AS lowest_salary,
    
    -- 最后一行值
    LAST_VALUE(salary) OVER (
        ORDER BY salary 
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
    ) AS highest_salary,
    
    -- 第 N 行值
    NTH_VALUE(salary, 3) OVER (ORDER BY salary) AS third_lowest,
    
    -- 前一行值
    LAG(salary) OVER (ORDER BY salary) AS prev_salary,
    LAG(salary, 2) OVER (ORDER BY salary) AS prev_2_salary,
    
    -- 后一行值
    LEAD(salary) OVER (ORDER BY salary) AS next_salary,
    LEAD(salary, 2, 0) OVER (ORDER BY salary) AS next_2_salary
FROM employees;

-- 命名窗口定义
SELECT 
    id,
    department_id,
    salary,
    RANK() OVER w_dept_salary AS dept_rank,
    AVG(salary) OVER w_dept AS dept_avg
FROM employees
WINDOW 
    w_dept AS (PARTITION BY department_id),
    w_dept_salary AS (w_dept ORDER BY salary DESC);
```

### 6.5 触发器

触发器在特定事件发生时自动执行函数。

```sql
-- 创建触发器函数
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建行级触发器
CREATE TRIGGER trg_employees_updated_at
    BEFORE UPDATE ON employees
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- 审计日志触发器
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100),
    operation VARCHAR(10),
    old_data JSONB,
    new_data JSONB,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(100)
);

CREATE OR REPLACE FUNCTION audit_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        INSERT INTO audit_log (table_name, operation, old_data, changed_by)
        VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(OLD), current_user);
        RETURN OLD;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO audit_log (table_name, operation, old_data, new_data, changed_by)
        VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(OLD), to_jsonb(NEW), current_user);
        RETURN NEW;
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO audit_log (table_name, operation, new_data, changed_by)
        VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(NEW), current_user);
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_employees_audit
    AFTER INSERT OR UPDATE OR DELETE ON employees
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger();

-- 语句级触发器
CREATE OR REPLACE FUNCTION log_dml_count()
RETURNS TRIGGER AS $$
DECLARE
    row_count INT;
BEGIN
    IF (TG_OP = 'INSERT') THEN
        GET DIAGNOSTICS row_count = ROW_COUNT;
        RAISE NOTICE 'Inserted % rows into %', row_count, TG_TABLE_NAME;
    ELSIF (TG_OP = 'UPDATE') THEN
        GET DIAGNOSTICS row_count = ROW_COUNT;
        RAISE NOTICE 'Updated % rows in %', row_count, TG_TABLE_NAME;
    ELSIF (TG_OP = 'DELETE') THEN
        GET DIAGNOSTICS row_count = ROW_COUNT;
        RAISE NOTICE 'Deleted % rows from %', row_count, TG_TABLE_NAME;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_dml
    AFTER INSERT OR UPDATE OR DELETE ON employees
    FOR EACH STATEMENT
    EXECUTE FUNCTION log_dml_count();

-- 条件触发器
CREATE TRIGGER trg_high_salary_alert
    AFTER INSERT OR UPDATE ON employees
    FOR EACH ROW
    WHEN (NEW.salary > 200000)
    EXECUTE FUNCTION notify_high_salary();

-- INSTEAD OF 触发器（用于视图）
CREATE VIEW employee_summary AS
SELECT department_id, COUNT(*) AS emp_count, AVG(salary) AS avg_salary
FROM employees
GROUP BY department_id;

CREATE OR REPLACE FUNCTION update_employee_summary()
RETURNS TRIGGER AS $$
BEGIN
    -- 处理对视图的 INSERT/UPDATE/DELETE
    RAISE EXCEPTION 'Cannot modify summary view directly';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_employee_summary
    INSTEAD OF INSERT OR UPDATE OR DELETE ON employee_summary
    FOR EACH ROW
    EXECUTE FUNCTION update_employee_summary();

-- 禁用/启用触发器
ALTER TABLE employees DISABLE TRIGGER trg_employees_updated_at;
ALTER TABLE employees ENABLE TRIGGER trg_employees_updated_at;

-- 删除触发器
DROP TRIGGER IF EXISTS trg_employees_updated_at ON employees;
```

### 6.6 存储过程和函数

```sql
-- 创建函数
CREATE OR REPLACE FUNCTION calculate_bonus(
    p_employee_id INT,
    p_bonus_percent NUMERIC
)
RETURNS NUMERIC AS $$
DECLARE
    v_salary NUMERIC;
    v_bonus NUMERIC;
BEGIN
    SELECT salary INTO v_salary 
    FROM employees 
    WHERE id = p_employee_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Employee % not found', p_employee_id;
    END IF;
    
    v_bonus := v_salary * (p_bonus_percent / 100);
    
    RETURN v_bonus;
END;
$$ LANGUAGE plpgsql;

-- 调用函数
SELECT calculate_bonus(1, 10);

-- 返回表的函数
CREATE OR REPLACE FUNCTION get_employees_by_dept(p_dept_id INT)
RETURNS TABLE (
    emp_id INT,
    full_name TEXT,
    emp_salary NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        id,
        first_name || ' ' || last_name,
        salary
    FROM employees
    WHERE department_id = p_dept_id;
END;
$$ LANGUAGE plpgsql;

-- 使用返回表的函数
SELECT * FROM get_employees_by_dept(1);

-- 存储过程（PostgreSQL 11+）
CREATE OR REPLACE PROCEDURE transfer_salary(
    p_from_emp_id INT,
    p_to_emp_id INT,
    p_amount NUMERIC
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_from_balance NUMERIC;
BEGIN
    -- 检查余额
    SELECT salary INTO v_from_balance 
    FROM employees WHERE id = p_from_emp_id;
    
    IF v_from_balance < p_amount THEN
        RAISE EXCEPTION 'Insufficient balance';
    END IF;
    
    -- 执行转账
    UPDATE employees SET salary = salary - p_amount WHERE id = p_from_emp_id;
    UPDATE employees SET salary = salary + p_amount WHERE id = p_to_emp_id;
    
    -- 记录日志
    INSERT INTO transfer_log (from_emp, to_emp, amount, transfer_time)
    VALUES (p_from_emp_id, p_to_emp_id, p_amount, CURRENT_TIMESTAMP);
    
    COMMIT;
END;
$$;

-- 调用存储过程
CALL transfer_salary(1, 2, 5000);

-- 带事务控制的存储过程
CREATE OR REPLACE PROCEDURE batch_update_salaries(
    p_increase_percent NUMERIC
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated_count INT := 0;
    v_batch_size INT := 1000;
    v_total_updated INT := 0;
BEGIN
    LOOP
        UPDATE employees 
        SET salary = salary * (1 + p_increase_percent / 100)
        WHERE id IN (
            SELECT id FROM employees 
            WHERE salary < 100000
            LIMIT v_batch_size
            FOR UPDATE SKIP LOCKED
        );
        
        GET DIAGNOSTICS v_updated_count = ROW_COUNT;
        v_total_updated := v_total_updated + v_updated_count;
        
        COMMIT;
        
        EXIT WHEN v_updated_count = 0;
    END LOOP;
    
    RAISE NOTICE 'Total employees updated: %', v_total_updated;
END;
$$;
```

### 6.7 物化视图

物化视图存储查询结果，可定期刷新。

```sql
-- 创建物化视图
CREATE MATERIALIZED VIEW mv_department_summary AS
SELECT 
    d.id AS department_id,
    d.name AS department_name,
    COUNT(e.id) AS employee_count,
    AVG(e.salary) AS avg_salary,
    MIN(e.salary) AS min_salary,
    MAX(e.salary) AS max_salary
FROM departments d
LEFT JOIN employees e ON d.id = e.department_id
GROUP BY d.id, d.name;

-- 创建物化视图索引
CREATE UNIQUE INDEX idx_mv_dept_summary_id ON mv_department_summary(department_id);

-- 刷新物化视图
REFRESH MATERIALIZED VIEW mv_department_summary;

-- 并发刷新（不阻塞读取，需要唯一索引）
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_department_summary;

-- 查看物化视图
SELECT * FROM mv_department_summary;

-- 删除物化视图
DROP MATERIALIZED VIEW IF EXISTS mv_department_summary;
```

---

## 第7章 复制与高可用

### 7.1 流复制（物理复制）

流复制是 PostgreSQL 的内置高可用方案，将主库的 WAL 日志实时传输到备库。

#### 7.1.1 主库配置

```ini
# postgresql.conf
listen_addresses = '*'
wal_level = replica              # 或 logical
max_wal_senders = 10             # 最大 WAL 发送进程数
wal_keep_size = 1GB              # 保留的 WAL 文件大小
max_replication_slots = 10       # 最大复制槽数
hot_standby = on                 # 允许备库查询
archive_mode = on                # 启用归档
archive_command = 'cp %p /archive/%f'  # 归档命令
```

```ini
# pg_hba.conf
# 允许复制连接
host    replication     replica_user    192.168.1.0/24      scram-sha-256
```

```sql
-- 创建复制用户
CREATE USER replica_user WITH REPLICATION ENCRYPTED PASSWORD 'strong_password';
```

#### 7.1.2 备库配置

```bash
# 1. 停止备库 PostgreSQL
sudo systemctl stop postgresql

# 2. 清空备库数据目录
rm -rf /var/lib/postgresql/17/main/*

# 3. 使用 pg_basebackup 克隆主库
pg_basebackup -h primary_host -p 5432 -U replica_user \
    -D /var/lib/postgresql/17/main \
    -Fp -Xs -P -R -v

# 参数说明：
# -Fp: 普通格式（不是 tar）
# -Xs: 流式 WAL
# -P: 显示进度
# -R: 创建 standby.signal 和连接配置
# -v: 详细输出
```

```ini
# postgresql.auto.conf（由 pg_basebackup 生成）
primary_conninfo = 'host=primary_host port=5432 user=replica_user password=strong_password'
```

#### 7.1.3 监控复制

```sql
-- 主库：查看复制状态
SELECT 
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    write_lag,
    flush_lag,
    replay_lag
FROM pg_stat_replication;

-- 备库：查看接收状态
SELECT 
    received_lsn,
    last_msg_send_time,
    last_msg_receipt_time,
    latest_end_lsn,
    latest_end_time
FROM pg_stat_wal_receiver;

-- 检查复制延迟
SELECT 
    EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) AS lag_seconds
FROM pg_stat_activity 
WHERE datname IS NULL;
```

#### 7.1.4 故障切换

```bash
# 在备库上执行提升
pg_ctl promote -D /var/lib/postgresql/17/main

# 或使用 SQL 命令（PostgreSQL 12+）
SELECT pg_promote();
```

### 7.2 逻辑复制

逻辑复制允许选择性地复制表，支持跨版本和异构复制。

#### 7.2.1 发布端配置

```ini
# postgresql.conf
wal_level = logical
max_replication_slots = 10
max_wal_senders = 10
```

```sql
-- 创建发布
CREATE PUBLICATION my_publication 
FOR TABLE employees, departments;

-- 创建发布（所有表）
CREATE PUBLICATION all_tables 
FOR ALL TABLES;

-- 创建发布（仅 INSERT）
CREATE PUBLICATION insert_only 
FOR TABLE audit_log 
WITH (publish = 'insert');

-- 查看发布
SELECT * FROM pg_publication;

-- 添加表到发布
ALTER PUBLICATION my_publication ADD TABLE projects;

-- 从发布移除表
ALTER PUBLICATION my_publication DROP TABLE projects;

-- 删除发布
DROP PUBLICATION my_publication;
```

#### 7.2.2 订阅端配置

```sql
-- 创建订阅
CREATE SUBSCRIPTION my_subscription
CONNECTION 'host=publisher_host port=5432 dbname=mydb user=replica_user password=password'
PUBLICATION my_publication;

-- 带选项的订阅
CREATE SUBSCRIPTION my_subscription
CONNECTION 'host=publisher_host port=5432 dbname=mydb user=replica_user password=password'
PUBLICATION my_publication
WITH (
    copy_data = true,           -- 复制现有数据
    create_slot = true,         -- 自动创建复制槽
    enabled = true,             -- 立即启用
    slot_name = 'my_slot'       -- 指定槽名称
);

-- 查看订阅状态
SELECT * FROM pg_subscription;
SELECT * FROM pg_stat_subscription;

-- 启用/禁用订阅
ALTER SUBSCRIPTION my_subscription ENABLE;
ALTER SUBSCRIPTION my_subscription DISABLE;

-- 刷新订阅（同步表结构变化）
ALTER SUBSCRIPTION my_subscription REFRESH PUBLICATION;

-- 删除订阅
DROP SUBSCRIPTION my_subscription;
```

### 7.3 高可用方案

#### 7.3.1 Patroni + etcd

Patroni 是一个用于 PostgreSQL 高可用的 Python 模板。

```yaml
# patroni.yml 示例
scope: postgres_cluster
namespace: /db/
name: node1

restapi:
  listen: 0.0.0.0:8008
  connect_address: 192.168.1.11:8008

etcd:
  hosts: 192.168.1.10:2379,192.168.1.11:2379,192.168.1.12:2379

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576
    master_start_timeout: 300
    synchronous_mode: false
    postgresql:
      use_pg_rewind: true
      parameters:
        wal_level: replica
        hot_standby: "on"
        wal_keep_size: 1GB
        max_wal_senders: 10
        max_replication_slots: 10
        wal_log_hints: "on"

postgresql:
  listen: 0.0.0.0:5432
  connect_address: 192.168.1.11:5432
  data_dir: /var/lib/postgresql/17/main
  bin_dir: /usr/lib/postgresql/17/bin
  authentication:
    replication:
      username: replica
      password: replica_pass
    superuser:
      username: postgres
      password: postgres_pass
```

#### 7.3.2 Repmgr

Repmgr 是另一个流行的 PostgreSQL 高可用工具。

```ini
# repmgr.conf
node_id=1
node_name=node1
conninfo='host=node1 dbname=repmgr user=repmgr password=password'
data_directory='/var/lib/postgresql/17/main'

failover=automatic
promote_command='repmgr standby promote -f /etc/repmgr.conf'
follow_command='repmgr standby follow -f /etc/repmgr.conf'

# 注册主库
repmgr -f /etc/repmgr.conf primary register

# 克隆备库
repmgr -h primary_host -U repmgr -d repmgr -f /etc/repmgr.conf standby clone

# 注册备库
repmgr -f /etc/repmgr.conf standby register

# 查看集群状态
repmgr -f /etc/repmgr.conf cluster show

# 手动切换
repmgr -f /etc/repmgr.conf standby switchover

# 故障切换
repmgr -f /etc/repmgr.conf standby promote
```

### 7.4 连接池

#### 7.4.1 PgBouncer

PgBouncer 是一个轻量级的 PostgreSQL 连接池。

```ini
; pgbouncer.ini
[databases]
mydb = host=localhost port=5432 dbname=mydb

[pgbouncer]
listen_port = 6432
listen_addr = 0.0.0.0
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
admin_users = postgres
stats_users = stats_collector

; 连接池模式
; session: 会话级（默认）
; transaction: 事务级
; statement: 语句级
pool_mode = transaction

; 连接池大小
default_pool_size = 25
max_client_conn = 10000
reserve_pool_size = 5
reserve_pool_timeout = 3

; 超时设置
server_idle_timeout = 600
server_lifetime = 3600
client_idle_timeout = 0
client_login_timeout = 60
```

```bash
# 启动 PgBouncer
pgbouncer -d /etc/pgbouncer/pgbouncer.ini

# 管理命令（连接到 pgbouncer 数据库）
psql -p 6432 pgbouncer -c "SHOW POOLS"
psql -p 6432 pgbouncer -c "SHOW CLIENTS"
psql -p 6432 pgbouncer -c "SHOW SERVERS"
psql -p 6432 pgbouncer -c "RELOAD"
```

---

## 第8章 性能调优与最佳实践

### 8.1 查询优化

#### 8.1.1 执行计划分析

```sql
-- 基本 EXPLAIN
EXPLAIN SELECT * FROM employees WHERE department_id = 1;

-- 详细执行计划
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM employees WHERE department_id = 1;

-- JSON 格式输出
EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
SELECT * FROM employees WHERE department_id = 1;

-- 关键指标解读
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT d.name, COUNT(e.id), AVG(e.salary)
FROM departments d
LEFT JOIN employees e ON d.id = e.department_id
WHERE e.hire_date > '2023-01-01'
GROUP BY d.name;
```

执行计划关键指标：

| 指标 | 说明 |
|------|------|
| cost | 预估成本（启动成本..总成本） |
| rows | 预估返回行数 |
| width | 预估平均行宽度（字节） |
| actual time | 实际执行时间 |
| loops | 循环次数 |
| Shared Hit | 从共享缓冲区读取的块数 |
| Shared Read | 从磁盘读取的块数 |

#### 8.1.2 查询优化技巧

```sql
-- 1. 避免 SELECT *
SELECT id, name, email FROM employees WHERE id = 1;

-- 2. 使用 LIMIT 限制结果
SELECT * FROM logs ORDER BY created_at DESC LIMIT 100;

-- 3. 使用合适的索引
CREATE INDEX idx_employees_dept_date ON employees(department_id, hire_date);

-- 4. 避免在索引列上使用函数
-- 低效
SELECT * FROM employees WHERE EXTRACT(YEAR FROM hire_date) = 2023;

-- 高效
SELECT * FROM employees 
WHERE hire_date >= '2023-01-01' AND hire_date < '2024-01-01';

-- 或使用函数索引
CREATE INDEX idx_employees_hire_year ON employees(EXTRACT(YEAR FROM hire_date));

-- 5. 使用 EXISTS 替代 IN（子查询）
-- 低效
SELECT * FROM departments 
WHERE id IN (SELECT department_id FROM employees WHERE salary > 100000);

-- 高效
SELECT * FROM departments d
WHERE EXISTS (
    SELECT 1 FROM employees e 
    WHERE e.department_id = d.id AND e.salary > 100000
);

-- 6. 使用 UNION ALL 替代 UNION（如果不需要去重）
SELECT id, name FROM employees_2023
UNION ALL
SELECT id, name FROM employees_2024;

-- 7. 批量操作替代循环
-- 低效：逐行更新
-- 高效：批量更新
UPDATE employees 
SET salary = salary * 1.1 
WHERE department_id = 1;

-- 8. 使用 COPY 替代 INSERT（大批量数据）
COPY employees FROM '/data/employees.csv' WITH (FORMAT csv, HEADER true);
```



### 8.2 备份恢复

**pg_dump逻辑备份**

```bash
# 备份整个数据库
pg_dump -U postgres -h localhost -d mydb > mydb_backup.sql

# 备份特定表
pg_dump -U postgres -d mydb -t users -t orders > tables_backup.sql

# 压缩备份
pg_dump -U postgres -d mydb | gzip > mydb_backup.sql.gz

# 自定义格式备份（支持并行和选择性恢复）
pg_dump -U postgres -d mydb -Fc -f mydb_backup.dump

# 并行备份
pg_dump -U postgres -d mydb -Fc -j 4 -f mydb_backup.dump

# 仅备份结构
pg_dump -U postgres -d mydb --schema-only > schema_backup.sql

# 仅备份数据
pg_dump -U postgres -d mydb --data-only > data_backup.sql
```

**pg_restore恢复**

```bash
# 恢复自定义格式备份
pg_restore -U postgres -d mydb mydb_backup.dump

# 恢复到新数据库
createdb -U postgres newdb
pg_restore -U postgres -d newdb mydb_backup.dump

# 仅恢复特定表
pg_restore -U postgres -d mydb -t users mydb_backup.dump

# 列出备份内容
pg_restore -l mydb_backup.dump

# 选择性恢复
pg_restore -U postgres -d mydb -L restore_list.txt mydb_backup.dump
```

**物理备份（pg_basebackup）**

```bash
# 全量物理备份
pg_basebackup -U replicator -D /backup/pg_backup -P -v

# 带WAL的备份
pg_basebackup -U replicator -D /backup/pg_backup -P -v -X stream

# 压缩备份
pg_basebackup -U replicator -D - -F tar -X stream | gzip > backup.tar.gz
```

**连续归档（PITR）**

```ini
# postgresql.conf 配置
wal_level = replica
archive_mode = on
archive_command = 'cp %p /archive/%f'
max_wal_senders = 3
```

**自动化备份脚本**

```bash
#!/bin/bash
# backup.sh - 自动化备份脚本

BACKUP_DIR="/backup/postgresql"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="mydb"
RETENTION_DAYS=7

# 创建备份目录
mkdir -p $BACKUP_DIR

# 执行备份
pg_dump -U postgres -d $DB_NAME -Fc -f "$BACKUP_DIR/${DB_NAME}_${DATE}.dump"

# 压缩
gzip "$BACKUP_DIR/${DB_NAME}_${DATE}.dump"

# 清理旧备份
find $BACKUP_DIR -name "${DB_NAME}_*.dump.gz" -mtime +$RETENTION_DAYS -delete

# 记录日志
echo "$(date): Backup completed - ${DB_NAME}_${DATE}.dump.gz" >> $BACKUP_DIR/backup.log
```


### 8.3 性能调优建议

**内存配置**

```ini
# postgresql.conf 内存调优

# 共享缓冲区 - 设为内存的25%
shared_buffers = 4GB

# 有效缓存大小 - 设为内存的50-75%
effective_cache_size = 12GB

# 每个查询操作的内存
work_mem = 256MB

# 维护操作内存
maintenance_work_mem = 1GB
```

**连接配置**

```ini
# 最大连接数
max_connections = 200

# 使用连接池（PgBouncer）
# 推荐配置：
# - 事务池模式
# - 默认池大小：20-50
# - 最大客户端连接：1000+
```

**WAL和检查点配置**

```ini
# WAL配置
wal_buffers = 16MB
wal_writer_delay = 200ms

# 检查点配置
checkpoint_timeout = 10min
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB
```

**查询优化配置**

```ini
# 并行查询
max_parallel_workers_per_gather = 4
max_parallel_workers = 8

# 随机页面成本（SSD设为1.1，HDD保持4.0）
random_page_cost = 1.1

# 有效IO并发（SSD设为200+）
effective_io_concurrency = 200
```

**监控和维护**

```sql
-- 查看慢查询
SELECT 
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    rows
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 查看表膨胀
SELECT 
    schemaname,
    tablename,
    n_tup_ins,
    n_tup_upd,
    n_tup_del,
    n_live_tup,
    n_dead_tup
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;

-- 查看索引使用情况
SELECT 
    schemaname,
    tablename,
    indexrelname,
    idx_scan,
    idx_tup_read
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- 手动VACUUM
VACUUM ANALYZE users;
VACUUM FULL users;  -- 完全整理（会锁表）

-- 自动VACUUM配置
autovacuum = on
autovacuum_vacuum_threshold = 50
autovacuum_vacuum_scale_factor = 0.2
autovacuum_analyze_threshold = 50
autovacuum_analyze_scale_factor = 0.1
```

**定期维护任务**

```sql
-- 1. 更新统计信息
ANALYZE;

-- 2. 清理死元组
VACUUM;

-- 3. 重建索引
REINDEX DATABASE mydb;

-- 4. 检查数据一致性
CHECKPOINT;
```

---

### 8.2 配置优化

#### 8.2.1 内存配置

```ini
# 根据服务器内存调整（假设 64GB 内存）

# 共享缓冲区（建议 25% 内存）
shared_buffers = 16GB

# 有效缓存大小（建议 50-75% 内存）
effective_cache_size = 48GB

# 工作内存（每个查询操作）
# 复杂查询需要更多，简单查询可以较少
work_mem = 128MB

# 维护工作内存（VACUUM, CREATE INDEX）
maintenance_work_mem = 2GB

# 自动工作内存（PostgreSQL 16+）
autovacuum_work_mem = 1GB
```

#### 8.2.2 WAL 配置

```ini
# WAL 级别
wal_level = replica

# WAL 缓冲区
wal_buffers = 16MB

# 检查点配置
checkpoint_timeout = 15min
checkpoint_completion_target = 0.9
max_wal_size = 8GB
min_wal_size = 2GB

# 异步提交（对数据一致性要求不高的场景）
synchronous_commit = off  # 或 local

# WAL 压缩（PostgreSQL 15+）
wal_compression = zstd
```

#### 8.2.3 并发配置

```ini
# 最大连接数
max_connections = 500

# 共享预加载库
shared_preload_libraries = 'pg_stat_statements,auto_explain'

# 并行查询
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4

# 自动清理
autovacuum = on
autovacuum_max_workers = 3
autovacuum_naptime = 1min
```

### 8.3 VACUUM 和 ANALYZE

```sql
-- 手动 VACUUM（回收空间）
VACUUM employees;

-- VACUUM 并分析
VACUUM ANALYZE employees;

-- 完全 VACUUM（会锁表）
VACUUM FULL employees;

-- 仅分析（更新统计信息）
ANALYZE employees;
ANALYZE employees (salary, department_id);  -- 仅特定列

-- 查看表的膨胀情况
SELECT 
    schemaname,
    tablename,
    n_tup_ins,
    n_tup_upd,
    n_tup_del,
    n_live_tup,
    n_dead_tup,
    ROUND(n_dead_tup * 100.0 / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY n_dead_tup DESC;

-- 查看自动清理状态
SELECT 
    relname,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze,
    vacuum_count,
    autovacuum_count
FROM pg_stat_user_tables
ORDER BY COALESCE(last_autovacuum, last_vacuum);
```

### 8.4 监控和诊断

```sql
-- 启用 pg_stat_statements
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 查看慢查询
SELECT 
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    rows,
    shared_blks_hit,
    shared_blks_read
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- 重置统计
SELECT pg_stat_statements_reset();

-- 查看当前活动
SELECT 
    pid,
    usename,
    datname,
    state,
    query_start,
    state_change,
    wait_event_type,
    wait_event,
    LEFT(query, 100) AS query_preview
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;

-- 查看锁等待
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.relation = blocked_locks.relation
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- 查看表和索引大小
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;

-- 查看数据库大小
SELECT 
    datname,
    pg_size_pretty(pg_database_size(datname)) AS size
FROM pg_database
ORDER BY pg_database_size(datname) DESC;
```

### 8.5 最佳实践清单

```sql
-- 1. 设计阶段
-- - 选择合适的数据类型
-- - 设计合理的索引策略
-- - 考虑分区（大表）
-- - 规范化设计，适度反规范化

-- 2. 开发阶段
-- - 使用参数化查询（防止 SQL 注入）
-- - 批量操作替代单条操作
-- - 合理使用事务
-- - 避免长事务

-- 3. 索引最佳实践
-- - 主键和外键自动创建索引
-- - 经常查询的列创建索引
-- - 避免过多索引（影响写入性能）
-- - 定期监控索引使用情况

-- 4. 查询最佳实践
-- - 只查询需要的列
-- - 使用 LIMIT 限制结果
-- - 避免在 WHERE 中使用函数
-- - 使用 EXPLAIN ANALYZE 分析查询

-- 5. 维护最佳实践
-- - 定期 VACUUM ANALYZE
-- - 监控表膨胀
-- - 定期重建索引
-- - 备份策略（pg_dump, pg_basebackup）

-- 6. 安全配置
-- - 使用强密码
-- - 限制网络访问
-- - 定期更新 PostgreSQL
-- - 启用 SSL 连接
```

---

## 第9章 PostgreSQL 16/17 新特性

### 9.1 PostgreSQL 16 新特性

#### 9.1.1 SQL/JSON 标准支持

```sql
-- JSON 构造函数
SELECT JSON_OBJECT('name': 'John', 'age': 30);
-- 结果: {"name": "John", "age": 30}

SELECT JSON_ARRAY(1, 2, 3, 'a', 'b');
-- 结果: [1, 2, 3, "a", "b"]

-- JSON 聚合
SELECT JSON_OBJECTAGG(column_name, data_type)
FROM information_schema.columns
WHERE table_name = 'employees';

-- JSON 路径查询增强
SELECT JSONB_PATH_QUERY(
    '{"a": [1, 2, 3, 4, 5]}',
    '$.a[*] ? (@ > 2)'
);
```

#### 9.1.2 并行聚合增强

```sql
-- PostgreSQL 16 支持更多并行聚合场景
-- 字符串聚合
EXPLAIN (ANALYZE, COSTS OFF)
SELECT department_id, STRING_AGG(name, ', ')
FROM employees
GROUP BY department_id;

-- 数组聚合
SELECT department_id, ARRAY_AGG(name ORDER BY name)
FROM employees
GROUP BY department_id;
```

#### 9.1.3 逻辑复制增强

```sql
-- 支持从备库进行逻辑复制
-- 配置参数
ALTER SYSTEM SET logical_replication_mode = 'on';

-- 双向复制支持
CREATE PUBLICATION bidirectional_pub FOR ALL TABLES
WITH (publish_via_partition_root = true);
```

#### 9.1.4 性能改进

```ini
# 自动压缩 TOAST 数据
default_toast_compression = lz4

# 改进的 vacuum 性能
vacuum_buffer_usage_limit = 2MB
```

### 9.2 PostgreSQL 17 新特性

#### 9.2.1 增量备份

```bash
# PostgreSQL 17 支持增量备份
# 完整备份
pg_basebackup -D /backup/full -Ft -z -P

# 增量备份（基于 WAL）
pg_basebackup -D /backup/incr -Ft -z -P \
    --incremental=/backup/full/manifest
```

#### 9.2.2 JSON 性能增强

```sql
-- JSONB 索引性能提升
-- 新的 JSONB 下标操作
SELECT ('{"a": {"b": 1}}'::jsonb)['a']['b'];
-- 结果: 1

-- JSONB 标量订阅
SELECT ('[1, 2, 3]'::jsonb)[1];
-- 结果: 2
```

#### 9.2.3 分区表增强

```sql
-- 默认分区支持 IDENTITY 列
CREATE TABLE measurements (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    logdate DATE NOT NULL,
    value NUMERIC
) PARTITION BY RANGE (logdate);

-- 分区路由优化
-- 更快的分区剪枝
EXPLAIN (ANALYZE, COSTS OFF)
SELECT * FROM measurements 
WHERE logdate = '2024-01-15';
```

#### 9.2.4 安全增强

```sql
-- 更严格的 SCRAM-SHA-256 认证
-- 配置参数
password_encryption = 'scram-sha-256'

-- 角色继承控制
CREATE ROLE app_user WITH NOINHERIT;
GRANT read_only TO app_user;
-- 需要显式 SET ROLE 来继承权限
```

#### 9.2.5 开发者体验改进

```sql
-- MERGE 语句增强
MERGE INTO target_table AS t
USING source_table AS s
ON t.id = s.id
WHEN MATCHED AND s.deleted THEN
    DELETE
WHEN MATCHED THEN
    UPDATE SET name = s.name, updated_at = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN
    INSERT (id, name) VALUES (s.id, s.name);

-- 更详细的错误信息
-- 使用 VERBOSE 选项获取更多信息
```

### 9.3 升级建议

```bash
# 使用 pg_upgrade 升级
pg_upgrade \
    --old-datadir=/var/lib/postgresql/16/main \
    --new-datadir=/var/lib/postgresql/17/main \
    --old-bindir=/usr/lib/postgresql/16/bin \
    --new-bindir=/usr/lib/postgresql/17/bin \
    --check  # 先检查

# 执行升级
pg_upgrade \
    --old-datadir=/var/lib/postgresql/16/main \
    --new-datadir=/var/lib/postgresql/17/main \
    --old-bindir=/usr/lib/postgresql/16/bin \
    --new-bindir=/usr/lib/postgresql/17/bin

# 使用逻辑复制升级（零停机）
# 1. 在 PostgreSQL 17 上创建订阅
# 2. 等待数据同步
# 3. 切换应用到新实例
# 4. 删除订阅
```

---

## 第10章 常见问题与解决方案

### 10.1 连接问题

```
问题: FATAL: sorry, too many clients already

解决方案:
1. 增加 max_connections
   ALTER SYSTEM SET max_connections = 500;
   
2. 使用连接池（PgBouncer）
   
3. 检查并关闭空闲连接
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' AND state_change < NOW() - INTERVAL '1 hour';
```

### 10.2 性能问题

```
问题: 查询执行缓慢

诊断步骤:
1. 查看执行计划
   EXPLAIN (ANALYZE, BUFFERS) SELECT ...
   
2. 检查是否使用索引
   - 关注 Seq Scan（全表扫描）
   - 检查索引是否存在
   
3. 检查表统计信息
   ANALYZE table_name;
   
4. 检查表膨胀
   SELECT n_dead_tup, n_live_tup FROM pg_stat_user_tables;
   
5. 检查锁等待
   SELECT * FROM pg_locks WHERE NOT granted;
```

### 10.3 磁盘空间问题

```sql
-- 问题: 磁盘空间不足

-- 1. 查找大表
SELECT 
    schemaname || '.' || tablename AS table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 20;

-- 2. 查找大索引
SELECT 
    schemaname || '.' || indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;

-- 3. 清理 WAL 文件
-- 确保归档已完成，然后:
SELECT pg_archive_cleanup('pg_wal', '000000010000000000000010');

-- 4. VACUUM FULL（会锁表）
VACUUM FULL large_table;

-- 5. 删除旧数据
DELETE FROM logs WHERE created_at < NOW() - INTERVAL '1 year';
VACUUM logs;
```

### 10.4 复制问题

```
问题: 复制延迟过大

诊断:
1. 查看复制状态
   SELECT * FROM pg_stat_replication;
   
2. 检查 WAL 发送进程
   SELECT * FROM pg_stat_activity WHERE query LIKE 'START_REPLICATION%';

解决方案:
1. 增加 wal_keep_size
   ALTER SYSTEM SET wal_keep_size = '2GB';
   
2. 检查网络带宽
   
3. 优化备库查询（避免长时间查询阻塞复制）
   SET hot_standby_feedback = on;
   
4. 如果 WAL 已被删除，需要重新初始化备库
   pg_basebackup -h primary -D /var/lib/postgresql/data -Fp -Xs -P -R
```

### 10.5 锁问题

```sql
-- 问题: 死锁或长时间锁等待

-- 1. 查看当前锁
SELECT 
    l.locktype,
    l.relation::regclass,
    l.mode,
    l.granted,
    a.usename,
    a.query,
    a.state
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE l.relation IS NOT NULL;

-- 2. 终止问题进程
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE query LIKE '%problematic_query%';

-- 3. 避免死锁的最佳实践
-- - 以固定顺序访问表
-- - 尽量缩短事务
-- - 使用适当的隔离级别
```

### 10.6 常用管理命令速查

```sql
-- 数据库管理
\l                          -- 列出所有数据库
\c database_name            -- 切换数据库
\dt                         -- 列出所有表
\d table_name               -- 查看表结构
\di                         -- 列出所有索引
\du                         -- 列出所有用户
\dn                         -- 列出所有 schema

-- 用户和权限
CREATE USER username WITH PASSWORD 'password';
GRANT SELECT ON table_name TO username;
GRANT ALL PRIVILEGES ON DATABASE dbname TO username;
REVOKE INSERT ON table_name FROM username;

-- 备份和恢复
-- 备份
pg_dump -h localhost -U postgres -d mydb -f backup.sql
pg_dump -h localhost -U postgres -d mydb -Ft -f backup.tar

-- 恢复
psql -h localhost -U postgres -d mydb -f backup.sql
pg_restore -h localhost -U postgres -d mydb backup.tar

-- 性能监控
SELECT * FROM pg_stat_activity;
SELECT * FROM pg_stat_database;
SELECT * FROM pg_stat_user_tables;
SELECT * FROM pg_stat_user_indexes;
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

-- 配置管理
SHOW all;                           -- 显示所有配置
SHOW shared_buffers;                -- 显示特定配置
ALTER SYSTEM SET param = value;     -- 修改配置
SELECT pg_reload_conf();            -- 重载配置
```

---

## 附录

### A. 参考资源

- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [PostgreSQL 中文社区](http://www.postgres.cn/)
- [pgAdmin - 图形化管理工具](https://www.pgadmin.org/)
- [PostgreSQL 扩展列表](https://pgxn.org/)

### B. 常用扩展

```sql
-- 常用扩展列表
CREATE EXTENSION pg_stat_statements;    -- SQL 统计
CREATE EXTENSION pg_trgm;               -- 模糊搜索
CREATE EXTENSION postgis;               -- 地理空间
CREATE EXTENSION uuid-ossp;             -- UUID 生成
CREATE EXTENSION hstore;                -- 键值对存储
CREATE EXTENSION citext;                -- 不区分大小写文本
CREATE EXTENSION unaccent;              -- 去除重音符号
CREATE EXTENSION tablefunc;             -- 交叉表
CREATE EXTENSION dblink;                -- 跨库查询
CREATE EXTENSION postgres_fdw;          -- 外部数据包装器
CREATE EXTENSION file_fdw;              -- 文件外部表
```

### C. 版本生命周期

| 版本 | 发布日期 | 最终支持日期 |
|------|----------|--------------|
| PostgreSQL 12 | 2019-10 | 2024-11 |
| PostgreSQL 13 | 2020-09 | 2025-11 |
| PostgreSQL 14 | 2021-09 | 2026-11 |
| PostgreSQL 15 | 2022-10 | 2027-11 |
| PostgreSQL 16 | 2023-09 | 2028-11 |
| PostgreSQL 17 | 2024-09 | 2029-11 |

---

  **适用版本**: PostgreSQL 14/15/16/17

---

*本文档内容基于 PostgreSQL 官方文档和最佳实践。如有疑问，请参考官方文档或社区资源。*
