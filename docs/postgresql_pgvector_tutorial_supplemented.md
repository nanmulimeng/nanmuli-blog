# PostgreSQL 向量数据库 pgvector 使用教程与功能详解

> **适用版本**: pgvector 0.8.0+  
> **PostgreSQL版本**: 14+ (推荐16或17)

---

## 目录

1. [向量数据库与pgvector简介](#第1章-向量数据库与pgvector简介)
2. [pgvector安装与配置](#第2章-pgvector安装与配置)
3. [核心概念详解](#第3章-核心概念详解)
4. [基础操作实战](#第4章-基础操作实战)
5. [索引与性能优化](#第5章-索引与性能优化)
6. [与AI框架集成](#第6章-与ai框架集成)
7. [Spring AI与pgvector集成详解](#第7章-spring-ai与pgvector集成详解)
8. [实际应用场景](#第8章-实际应用场景)
9. [最佳实践与性能调优](#第9章-最佳实践与性能调优)
10. [常见问题与解决方案](#第10章-常见问题与解决方案)

---

## 第1章 向量数据库与pgvector简介

### 1.1 什么是向量数据库

向量数据库是一种专门设计用于存储、索引和查询高维向量数据的数据库系统。与传统关系型数据库不同，向量数据库的核心能力是**相似度搜索（Similarity Search）**，即在海量向量数据中快速找到与查询向量最相似的向量。

#### 向量数据库的核心特点

| 特性 | 说明 |
|------|------|
| **高维向量存储** | 支持数百到数千维的浮点数向量 |
| **相似度计算** | 内置多种距离度量算法（欧氏距离、余弦相似度等） |
| **近似最近邻搜索（ANN）** | 通过索引加速大规模向量检索 |
| **与AI/ML集成** | 无缝对接嵌入模型，支持语义搜索 |

#### 向量数据库的应用场景

- **语义搜索（Semantic Search）**：理解查询意图，返回语义相关结果
- **推荐系统（Recommendation Systems）**：基于用户行为向量进行相似推荐
- **图像/视频检索**：通过特征向量实现以图搜图
- **RAG（检索增强生成）**：为大语言模型提供外部知识检索
- **异常检测**：识别与正常模式偏离的向量

### 1.2 pgvector简介

**pgvector** 是 PostgreSQL 的开源向量相似性搜索扩展，它将向量数据库的能力无缝集成到 PostgreSQL 中。

#### pgvector的核心优势

1. **原生PostgreSQL集成**：作为扩展存在，无需单独部署向量数据库
2. **ACID兼容**：继承PostgreSQL的事务、并发控制和数据完整性保证
3. **丰富的数据类型**：支持 `vector`、`halfvec`、`bit`、`sparsevec` 等多种向量类型
4. **多种距离函数**：内置L2、余弦、内积、汉明、Jaccard等距离度量
5. **高效索引**：支持IVFFlat和HNSW两种近似最近邻索引
6. **与生态集成**：完美支持LangChain、Spring AI、OpenAI等主流框架

#### pgvector支持的向量类型

```
┌─────────────┬──────────────┬────────────────────────────────┐
│ 类型        │ 最大维度     │ 说明                           │
├─────────────┼──────────────┼────────────────────────────────┤
│ vector      │ 16,000       │ 标准浮点向量（默认）            │
│ halfvec     │ 4,000        │ 半精度浮点向量（节省存储）      │
│ bit         │ 64,000       │ 二进制向量（用于哈希/签名）     │
│ sparsevec   │ 1,000        │ 稀疏向量（高效存储稀疏数据）    │
└─────────────┴──────────────┴────────────────────────────────┘
```

#### pgvector版本演进

| 版本 | 主要特性 |
|------|----------|
| v0.5.0 | HNSW索引支持 |
| v0.6.0 | 并行索引构建、性能优化 |
| v0.7.0 | sparsevec类型、更多距离函数 |
| v0.8.0 | 性能大幅提升、新距离函数 |

---

## 第2章 pgvector安装与配置

### 2.1 环境要求

- **PostgreSQL**: 14+ (推荐16或17)
- **操作系统**: Linux、macOS、Windows (WSL)
- **编译工具**: GCC、Make (源码安装时需要)

### 2.2 Docker安装（推荐）

Docker是安装pgvector最简单快捷的方式，适合开发和测试环境。

#### 基本启动命令

```bash
# 使用官方镜像启动PostgreSQL + pgvector
docker run -d \
  --name pgvector \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=vectordb \
  -p 5432:5432 \
  pgvector/pgvector:pg17
```

#### 生产环境配置

```bash
# 生产环境推荐配置
docker run -d \
  --name pgvector-prod \
  --restart unless-stopped \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=YourStrongPassword \
  -e POSTGRES_DB=vectordb \
  -e PGDATA=/var/lib/postgresql/data/pgdata \
  -v /data/postgres:/var/lib/postgresql/data \
  -p 5432:5432 \
  --shm-size=256m \
  pgvector/pgvector:pg17 \
  -c shared_buffers=2GB \
  -c effective_cache_size=6GB \
  -c work_mem=256MB \
  -c maintenance_work_mem=512MB
```

#### Docker Compose配置

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg17
    container_name: pgvector-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: vectordb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    command: >
      postgres
      -c shared_buffers=1GB
      -c effective_cache_size=3GB
      -c work_mem=128MB
      -c maintenance_work_mem=256MB
      -c max_connections=200
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

### 2.3 源码编译安装

源码安装适合需要自定义配置或使用特定PostgreSQL版本的场景。

#### 步骤1：安装依赖

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y postgresql-server-dev-16 build-essential git

# CentOS/RHEL
sudo yum install -y postgresql16-devel gcc make git

# macOS
brew install postgresql@16
```

#### 步骤2：下载并编译pgvector

```bash
# 克隆指定版本
git clone --branch v0.8.0 https://github.com/pgvector/pgvector.git
cd pgvector

# 编译
make

# 安装（需要root权限）
sudo make install
```

#### 步骤3：验证安装

```bash
# 连接到PostgreSQL
psql -U postgres

-- 查看可用扩展
SELECT * FROM pg_available_extensions WHERE name = 'vector';

-- 输出示例
--   name   │ default_version │ installed_version │                              comment
-- ---------+-----------------+-------------------+--------------------------------------------------------------------
--  vector  │ 0.8.0           │                   │ vector data type and ivfflat and hnsw access methods
```

### 2.4 包管理器安装

#### Ubuntu/Debian

```bash
# 添加PostgreSQL官方仓库
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update

# 安装pgvector
sudo apt-get install -y postgresql-16-pgvector

# 对于PostgreSQL 17
sudo apt-get install -y postgresql-17-pgvector
```

#### CentOS/RHEL

```bash
# 添加PostgreSQL仓库
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm

# 安装pgvector
sudo dnf install -y pgvector_16
```

#### macOS (Homebrew)

```bash
# 安装PostgreSQL
brew install postgresql@16

# 安装pgvector
brew install pgvector
```

### 2.5 启用pgvector扩展

安装完成后，需要在数据库中启用扩展：

```sql
-- 连接到目标数据库
\c vectordb

-- 启用pgvector扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 验证扩展已启用
SELECT * FROM pg_extension WHERE extname = 'vector';

-- 查看pgvector版本
SELECT extversion FROM pg_extension WHERE extname = 'vector';

-- 查看向量操作符
SELECT oprname, oprleft::regtype, oprright::regtype 
FROM pg_operator 
WHERE oprname IN ('<->', '<#>', '<=>', '<+>', '<~>', '<%>');
```

### 2.6 常用辅助扩展

```sql
-- UUID生成（推荐用于主键）
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 键值存储（用于存储元数据）
CREATE EXTENSION IF NOT EXISTS hstore;

-- JSON处理增强
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 全文搜索
CREATE EXTENSION IF NOT EXISTS pg_search;
```

---

## 第3章 核心概念详解

### 3.1 向量数据类型

pgvector提供了多种向量数据类型，以适应不同的应用场景。

#### 3.1.1 vector（标准浮点向量）

```sql
-- 创建向量列（指定维度）
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(1536)  -- OpenAI Ada-002的维度
);

-- 插入向量数据
INSERT INTO documents (content, embedding) 
VALUES (
    '这是一篇关于人工智能的文章',
    '[0.1, 0.2, 0.3, ..., 0.001]'::vector  -- 1536维向量
);

-- 查看向量维度
SELECT embedding, vector_dims(embedding) FROM documents LIMIT 1;
```

#### 3.1.2 halfvec（半精度向量）

```sql
-- halfvec使用16位浮点数，节省50%存储空间
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    description TEXT,
    embedding halfvec(768)  -- BERT-base的维度
);

-- 从vector转换为halfvec
INSERT INTO products (name, embedding)
SELECT name, embedding::halfvec 
FROM source_table;

-- 注意：halfvec精度较低，适合对精度要求不高的场景
```

#### 3.1.3 bit（二进制向量）

```sql
-- bit类型存储二进制向量，适合局部敏感哈希(LSH)
CREATE TABLE image_signatures (
    id SERIAL PRIMARY KEY,
    image_path VARCHAR(500),
    signature bit(256)  -- 256位二进制签名
);

-- 插入二进制向量
INSERT INTO image_signatures (image_path, signature)
VALUES ('/path/to/image.jpg', '1010101010101010...'::bit(256));

-- 汉明距离计算
SELECT * FROM image_signatures 
ORDER BY signature <~> '1010101010101010...'::bit(256) 
LIMIT 10;
```

#### 3.1.4 sparsevec（稀疏向量）

```sql
-- sparsevec高效存储稀疏向量（大部分值为0）
CREATE TABLE sparse_embeddings (
    id SERIAL PRIMARY KEY,
    embedding sparsevec(10000)  -- 10000维，但只有少数非零值
);

-- 稀疏向量格式：{索引:值, 索引:值, ...}/维度
INSERT INTO sparse_embeddings (embedding)
VALUES ('{1:0.5, 100:0.3, 5000:0.8}/10000'::sparsevec);

-- 稀疏向量会自动压缩存储
```

### 3.2 距离函数详解

pgvector提供了多种距离度量函数，适用于不同的相似度计算场景。

#### 距离函数对照表

| 操作符 | 函数名 | 距离类型 | 适用场景 | 返回值范围 |
|--------|--------|----------|----------|------------|
| `<->` | l2_distance | 欧几里得距离(L2) | 通用相似度 | [0, +∞) |
| `<#>` | inner_product | 负内积 | 推荐系统 | (-∞, +∞) |
| `<=>` | cosine_distance | 余弦距离 | 文本/语义搜索 | [0, 2] |
| `<+>` | l1_distance | 曼哈顿距离(L1) | 稀疏数据 | [0, +∞) |
| `<~>` | hamming_distance | 汉明距离 | 二进制向量 | [0, n] |
| `<%>` | jaccard_distance | Jaccard距离 | 集合相似度 | [0, 1] |

#### 3.2.1 欧几里得距离 (L2 Distance)

```sql
-- L2距离：向量间的直线距离
-- 公式：sqrt(sum((a_i - b_i)^2))

-- 示例：查找最相似的向量
SELECT 
    id, 
    content,
    embedding <-> '[0.1, 0.2, 0.3]'::vector AS distance
FROM documents
ORDER BY distance
LIMIT 5;

-- 使用索引的L2距离查询
CREATE INDEX ON documents USING hnsw (embedding vector_l2_ops);

SELECT * FROM documents 
ORDER BY embedding <-> query_vector 
LIMIT 10;
```

#### 3.2.2 余弦距离 (Cosine Distance)

```sql
-- 余弦距离：1 - 余弦相似度
-- 公式：1 - (A·B) / (||A|| * ||B||)
-- 范围：[0, 2]，0表示完全相同方向

-- 余弦距离最适合文本嵌入（已归一化的向量）
SELECT 
    id,
    content,
    embedding <=> query_embedding AS cosine_distance,
    1 - (embedding <=> query_embedding) AS cosine_similarity
FROM documents
ORDER BY cosine_distance
LIMIT 10;

-- 创建余弦距离索引
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);
```

#### 3.2.3 内积 (Inner Product)

```sql
-- 负内积：用于最大化相似度的场景
-- 注意：pgvector使用<#>表示负内积，所以ORDER BY ... <#> ... ASC

-- 推荐系统中常用
SELECT 
    product_id,
    product_name,
    embedding <#> user_preference_vector AS negative_inner_product
FROM products
ORDER BY negative_inner_product ASC  -- 越小表示越相似
LIMIT 20;

-- 创建内积索引
CREATE INDEX ON products USING hnsw (embedding vector_ip_ops);
```

#### 3.2.4 曼哈顿距离 (L1 Distance)

```sql
-- L1距离：各维度差值的绝对值之和
-- 公式：sum(|a_i - b_i|)

SELECT 
    id,
    embedding <+> '[0.1, 0.2, 0.3]'::vector AS l1_distance
FROM documents
ORDER BY l1_distance
LIMIT 10;
```

#### 3.2.5 汉明距离 (Hamming Distance)

```sql
-- 汉明距离：两个二进制向量不同位的数量
-- 仅适用于bit类型

SELECT 
    id,
    signature <~> '10101010...'::bit(256) AS hamming_distance
FROM image_signatures
ORDER BY hamming_distance
LIMIT 10;

-- 创建汉明距离索引
CREATE INDEX ON image_signatures USING hnsw (signature bit_hamming_ops);
```

### 3.3 相似度计算原理

#### 3.3.1 向量归一化

```sql
-- 余弦相似度计算前，通常需要归一化向量
-- pgvector提供vector_norm函数

-- 归一化向量
SELECT embedding / vector_norm(embedding) AS normalized_embedding
FROM documents;

-- 创建归一化视图
CREATE VIEW normalized_documents AS
SELECT 
    id,
    content,
    embedding / vector_norm(embedding) AS normalized_embedding
FROM documents;
```

#### 3.3.2 批量相似度计算

```sql
-- 计算两个向量集合之间的相似度矩阵
WITH query_vectors AS (
    SELECT 1 AS query_id, '[0.1, 0.2, 0.3]'::vector AS vec
    UNION ALL
    SELECT 2, '[0.4, 0.5, 0.6]'::vector
),
doc_vectors AS (
    SELECT id, embedding FROM documents
)
SELECT 
    q.query_id,
    d.id AS doc_id,
    d.embedding <=> q.vec AS cosine_distance
FROM query_vectors q
CROSS JOIN doc_vectors d
ORDER BY q.query_id, cosine_distance;
```

---

## 第4章 基础操作实战

### 4.1 创建向量表

#### 4.1.1 基础向量表

```sql
-- 创建简单的向量表
CREATE TABLE embeddings (
    id SERIAL PRIMARY KEY,
    text_content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 添加注释
COMMENT ON TABLE embeddings IS '存储文本嵌入向量';
COMMENT ON COLUMN embeddings.embedding IS 'OpenAI Ada-002生成的1536维向量';
```

#### 4.1.2 带元数据的向量表

```sql
-- 创建带丰富元数据的向量表
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- 内容相关
    title VARCHAR(500),
    content TEXT NOT NULL,
    content_type VARCHAR(50) DEFAULT 'article',  -- article, faq, doc
    
    -- 向量数据
    embedding vector(1536) NOT NULL,
    
    -- 分类和标签
    category VARCHAR(100),
    tags TEXT[],
    
    -- 来源信息
    source_url VARCHAR(1000),
    source_title VARCHAR(500),
    
    -- 权限和时间
    access_level VARCHAR(20) DEFAULT 'public',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 额外元数据（JSON格式）
    metadata JSONB DEFAULT '{}'
);

-- 创建索引
CREATE INDEX idx_kb_category ON knowledge_base(category);
CREATE INDEX idx_kb_tags ON knowledge_base USING GIN(tags);
CREATE INDEX idx_kb_metadata ON knowledge_base USING GIN(metadata);
CREATE INDEX idx_kb_created_at ON knowledge_base(created_at DESC);
```

#### 4.1.3 分区向量表（大数据量）

```sql
-- 对于超大规模数据，使用分区表
CREATE TABLE embeddings_partitioned (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    category VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (created_at);

-- 创建月度分区
CREATE TABLE embeddings_y2024m01 PARTITION OF embeddings_partitioned
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
    
CREATE TABLE embeddings_y2024m02 PARTITION OF embeddings_partitioned
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- 自动创建分区的函数
CREATE OR REPLACE FUNCTION create_monthly_partition()
RETURNS void AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    partition_date := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month');
    partition_name := 'embeddings_y' || TO_CHAR(partition_date, 'YYYY') || 'm' || TO_CHAR(partition_date, 'MM');
    start_date := partition_date;
    end_date := partition_date + INTERVAL '1 month';
    
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF embeddings_partitioned FOR VALUES FROM (%L) TO (%L)',
                   partition_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;
```

### 4.2 插入向量数据

#### 4.2.1 单条插入

```sql
-- 直接插入向量
INSERT INTO embeddings (text_content, embedding)
VALUES (
    'PostgreSQL是一个强大的开源关系型数据库',
    '[0.023, -0.045, 0.123, ..., 0.056]'::vector
);

-- 使用数组转换
INSERT INTO embeddings (text_content, embedding)
VALUES (
    '向量数据库用于相似度搜索',
    ARRAY[0.1, 0.2, 0.3]::vector
);
```

#### 4.2.2 批量插入

```sql
-- 批量插入提高性能
INSERT INTO embeddings (text_content, embedding) VALUES
    ('文本1', '[0.1, 0.2, ...]'::vector),
    ('文本2', '[0.3, 0.4, ...]'::vector),
    ('文本3', '[0.5, 0.6, ...]'::vector);

-- 使用COPY命令（最快的方式）
-- 准备CSV文件：content,embedding
-- "文本1","[0.1,0.2,0.3]"
-- "文本2","[0.4,0.5,0.6]"

COPY embeddings(text_content, embedding) 
FROM '/path/to/vectors.csv' 
WITH (FORMAT csv, HEADER true);
```

#### 4.2.3 从其他表导入

```sql
-- 从另一个表导入并转换
INSERT INTO embeddings (text_content, embedding)
SELECT 
    article_content,
    embedding_vector::vector(1536)
FROM source_articles
WHERE article_content IS NOT NULL
  AND embedding_vector IS NOT NULL;

-- 使用CTE批量处理
WITH new_embeddings AS (
    SELECT 
        id,
        content,
        generate_embedding(content) AS embedding  -- 假设有生成函数
    FROM raw_content
    WHERE id NOT IN (SELECT source_id FROM embeddings)
)
INSERT INTO embeddings (source_id, text_content, embedding)
SELECT id, content, embedding FROM new_embeddings;
```

### 4.3 相似度查询

#### 4.3.1 基础相似度搜索

```sql
-- 查找最相似的5条记录
SELECT 
    id,
    text_content,
    embedding <=> '[0.1, 0.2, 0.3]'::vector AS distance
FROM embeddings
ORDER BY embedding <=> '[0.1, 0.2, 0.3]'::vector
LIMIT 5;

-- 使用参数化查询（推荐）
PREPARE search_similar (vector) AS
SELECT 
    id,
    text_content,
    embedding <=> $1 AS distance
FROM embeddings
ORDER BY embedding <=> $1
LIMIT 10;

EXECUTE search_similar('[0.1, 0.2, 0.3]'::vector);
```

#### 4.3.2 带过滤条件的相似度搜索

```sql
-- 按类别过滤
SELECT 
    id,
    title,
    content,
    embedding <=> query_embedding AS distance
FROM knowledge_base
WHERE category = '技术文档'
  AND access_level = 'public'
ORDER BY embedding <=> query_embedding
LIMIT 10;

-- 按标签过滤
SELECT 
    id,
    title,
    embedding <=> query_embedding AS distance
FROM knowledge_base
WHERE tags && ARRAY['postgresql', 'database']  -- 包含任一标签
ORDER BY embedding <=> query_embedding
LIMIT 10;

-- 按时间范围过滤
SELECT 
    id,
    title,
    embedding <=> query_embedding AS distance
FROM knowledge_base
WHERE created_at > CURRENT_DATE - INTERVAL '30 days'
ORDER BY embedding <=> query_embedding
LIMIT 10;

-- 组合过滤条件
SELECT 
    id,
    title,
    content,
    embedding <=> query_embedding AS distance
FROM knowledge_base
WHERE category = 'FAQ'
  AND access_level = 'public'
  AND tags @> ARRAY['pgvector']
  AND metadata->>'language' = 'zh-CN'
ORDER BY embedding <=> query_embedding
LIMIT 5;
```

#### 4.3.3 相似度阈值过滤

```sql
-- 只返回相似度高于阈值的记录
WITH similarity_search AS (
    SELECT 
        id,
        title,
        content,
        embedding <=> query_embedding AS distance,
        1 - (embedding <=> query_embedding) AS similarity
    FROM knowledge_base
)
SELECT * FROM similarity_search
WHERE similarity > 0.8  -- 相似度阈值
ORDER BY distance
LIMIT 10;

-- 创建相似度搜索函数
CREATE OR REPLACE FUNCTION search_by_similarity(
    query_vector vector,
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    title VARCHAR,
    content TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        kb.id,
        kb.title,
        kb.content,
        (1 - (kb.embedding <=> query_vector))::FLOAT AS similarity
    FROM knowledge_base kb
    WHERE (1 - (kb.embedding <=> query_vector)) > similarity_threshold
    ORDER BY kb.embedding <=> query_vector
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- 使用函数
SELECT * FROM search_by_similarity('[0.1, 0.2, ...]'::vector, 0.8, 5);
```

### 4.4 更新和删除操作

```sql
-- 更新向量
UPDATE embeddings
SET 
    embedding = '[0.5, 0.6, 0.7]'::vector,
    updated_at = CURRENT_TIMESTAMP
WHERE id = 1;

-- 批量更新
UPDATE embeddings
SET embedding = new_vectors.embedding
FROM new_vectors
WHERE embeddings.id = new_vectors.id;

-- 删除向量
DELETE FROM embeddings WHERE id = 1;

-- 删除相似度低的记录（清理）
DELETE FROM embeddings
WHERE id IN (
    SELECT id FROM embeddings
    WHERE embedding <=> reference_vector > 1.5
);
```

### 4.5 向量聚合操作

```sql
-- 计算平均向量
SELECT AVG(embedding) AS avg_embedding
FROM embeddings
WHERE category = '技术';

-- 向量求和
SELECT SUM(embedding) AS sum_embedding
FROM embeddings
WHERE created_at > CURRENT_DATE - INTERVAL '7 days';

-- 分组聚合
SELECT 
    category,
    COUNT(*) AS count,
    AVG(embedding) AS center_vector
FROM embeddings
GROUP BY category;
```

---

## 第5章 索引与性能优化

### 5.1 索引类型对比

pgvector支持两种主要的近似最近邻（ANN）索引：IVFFlat和HNSW。

| 特性 | IVFFlat | HNSW |
|------|---------|------|
| **构建速度** | 快 | 慢 |
| **查询速度** | 中等 | 快 |
| **内存占用** | 低 | 高 |
| **召回率** | 依赖lists参数 | 高 |
| **更新开销** | 需要重建 | 支持增量更新 |
| **推荐场景** | 静态数据集 | 动态数据集 |

### 5.2 IVFFlat索引

IVFFlat（Inverted File with Flat Compression）将向量空间划分为多个簇（lists），查询时只搜索最相关的簇。

#### 5.2.1 创建IVFFlat索引

```sql
-- 基本语法
CREATE INDEX ON table_name 
USING ivfflat (column_name distance_ops) 
WITH (lists = N);

-- L2距离索引
CREATE INDEX idx_embeddings_l2 
ON embeddings 
USING ivfflat (embedding vector_l2_ops) 
WITH (lists = 100);

-- 余弦距离索引
CREATE INDEX idx_embeddings_cosine 
ON embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- 内积索引
CREATE INDEX idx_embeddings_ip 
ON embeddings 
USING ivfflat (embedding vector_ip_ops) 
WITH (lists = 100);
```

#### 5.2.2 lists参数设置

```sql
-- lists参数决定了簇的数量
-- 推荐设置：
-- - 数据量 < 100万: lists = 行数 / 1000
-- - 数据量 >= 100万: lists = sqrt(行数)

-- 示例：10万条数据
CREATE INDEX idx_embeddings_ivfflat 
ON embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);  -- 100000 / 1000 = 100

-- 示例：500万条数据
CREATE INDEX idx_embeddings_ivfflat 
ON embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 2236);  -- sqrt(5000000) ≈ 2236
```

#### 5.2.3 probes参数调优

```sql
-- probes参数控制查询时搜索的簇数量
-- 默认值：1
-- 推荐值：lists的1/10到1/5

-- 设置会话级别的probes
SET ivfflat.probes = 10;

-- 或者在查询中设置
SET LOCAL ivfflat.probes = 10;
SELECT * FROM embeddings 
ORDER BY embedding <=> query_vector 
LIMIT 10;

-- 权衡：probes越大，召回率越高，但查询越慢
```

### 5.3 HNSW索引

HNSW（Hierarchical Navigable Small World）是一种基于图的索引结构，查询性能优秀，支持增量更新。

#### 5.3.1 创建HNSW索引

```sql
-- 基本语法
CREATE INDEX ON table_name 
USING hnsw (column_name distance_ops);

-- L2距离HNSW索引
CREATE INDEX idx_embeddings_hnsw_l2 
ON embeddings 
USING hnsw (embedding vector_l2_ops);

-- 余弦距离HNSW索引（推荐）
CREATE INDEX idx_embeddings_hnsw_cosine 
ON embeddings 
USING hnsw (embedding vector_cosine_ops);

-- 内积HNSW索引
CREATE INDEX idx_embeddings_hnsw_ip 
ON embeddings 
USING hnsw (embedding vector_ip_ops);

-- 带参数的HNSW索引
CREATE INDEX idx_embeddings_hnsw 
ON embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (
    m = 16,              -- 每个节点的最大连接数
    ef_construction = 64  -- 构建时的搜索宽度
);
```

#### 5.3.2 HNSW参数说明

| 参数 | 说明 | 默认值 | 推荐值 |
|------|------|--------|--------|
| m | 每个节点的最大连接数 | 16 | 8-32 |
| ef_construction | 构建时的搜索宽度 | 64 | 64-200 |
| ef_search | 查询时的搜索宽度 | 40 | 动态设置 |

```sql
-- 设置ef_search参数
SET hnsw.ef_search = 100;

-- 或者在查询中设置
SET LOCAL hnsw.ef_search = 100;
SELECT * FROM embeddings 
ORDER BY embedding <=> query_vector 
LIMIT 10;

-- ef_search越大，召回率越高，查询越慢
-- 推荐：ef_search >= limit + 额外余量
```

### 5.4 索引选择建议

```sql
-- 决策流程：
-- 1. 数据量小（< 10万）：可以不建索引，顺序扫描即可
-- 2. 数据静态或更新少：IVFFlat
-- 3. 数据动态更新频繁：HNSW
-- 4. 追求极致查询性能：HNSW

-- 实际建议：
-- 生产环境推荐HNSW，除非内存受限
```

### 5.5 性能优化技巧

#### 5.5.1 查询优化

```sql
-- 1. 使用LIMIT限制返回数量
SELECT * FROM embeddings 
ORDER BY embedding <=> query_vector 
LIMIT 10;  -- 不要省略LIMIT

-- 2. 先过滤再排序
SELECT * FROM embeddings 
WHERE category = '技术'  -- 先过滤减少数据量
ORDER BY embedding <=> query_vector 
LIMIT 10;

-- 3. 使用覆盖索引
CREATE INDEX idx_covering 
ON embeddings USING hnsw (embedding vector_cosine_ops)
INCLUDE (id, title);  -- 包含常用查询列
```

#### 5.5.2 并行查询

```sql
-- 启用并行查询
SET max_parallel_workers_per_gather = 4;

-- 对于大数据量的顺序扫描，PostgreSQL会自动并行化
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM embeddings 
ORDER BY embedding <=> query_vector 
LIMIT 100;
```

#### 5.5.3 内存配置

```sql
-- postgresql.conf推荐配置

-- 共享缓冲区（推荐设置为内存的25%）
shared_buffers = 2GB

-- 有效缓存大小（推荐设置为内存的50-75%）
effective_cache_size = 6GB

-- 工作内存（复杂查询使用）
work_mem = 256MB

-- 维护工作内存（索引构建使用）
maintenance_work_mem = 512MB
```

### 5.6 索引维护

```sql
-- 查看索引大小
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) AS index_size
FROM pg_indexes
WHERE tablename = 'embeddings';

-- 重建索引
REINDEX INDEX idx_embeddings_hnsw;

-- 分析表（更新统计信息）
ANALYZE embeddings;

-- 清理死元组
VACUUM ANALYZE embeddings;

-- 监控索引使用情况
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,      -- 索引扫描次数
    idx_tup_read,  -- 通过索引读取的元组数
    idx_tup_fetch  -- 通过索引获取的元组数
FROM pg_stat_user_indexes
WHERE tablename = 'embeddings';
```

---

## 第6章 与AI框架集成

### 6.1 OpenAI嵌入集成

#### 6.1.1 生成嵌入向量

```python
# Python示例：使用OpenAI API生成嵌入
import openai
import psycopg2
from psycopg2.extras import execute_values

# 配置OpenAI
openai.api_key = "your-api-key"

def generate_embedding(text):
    """生成文本的嵌入向量"""
    response = openai.Embedding.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

# 示例：生成单个文本的嵌入
text = "PostgreSQL是一个强大的开源数据库"
embedding = generate_embedding(text)
print(f"维度: {len(embedding)}")  # 输出: 1536
```

#### 6.1.2 批量存储到pgvector

```python
# 批量生成和存储嵌入
def store_documents(documents):
    """批量存储文档和嵌入"""
    # 生成嵌入
    texts = [doc['content'] for doc in documents]
    response = openai.Embedding.create(
        input=texts,
        model="text-embedding-ada-002"
    )
    
    # 准备数据
    data = []
    for i, doc in enumerate(documents):
        embedding = response['data'][i]['embedding']
        data.append((
            doc['title'],
            doc['content'],
            embedding,
            doc.get('category', 'general')
        ))
    
    # 插入数据库
    conn = psycopg2.connect(
        host="localhost",
        database="vectordb",
        user="postgres",
        password="postgres"
    )
    
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO knowledge_base (title, content, embedding, category)
            VALUES %s
            """,
            data,
            template="(%s, %s, %s::vector, %s)"
        )
    conn.commit()
    conn.close()

# 使用示例
docs = [
    {"title": "PostgreSQL介绍", "content": "PostgreSQL是...", "category": "数据库"},
    {"title": "pgvector安装", "content": "pgvector可以通过...", "category": "教程"}
]
store_documents(docs)
```

#### 6.1.3 语义搜索实现

```python
# 语义搜索函数
def semantic_search(query, top_k=5, category=None):
    """基于语义的文档搜索"""
    # 生成查询嵌入
    query_embedding = generate_embedding(query)
    
    conn = psycopg2.connect(
        host="localhost",
        database="vectordb",
        user="postgres",
        password="postgres"
    )
    
    with conn.cursor() as cur:
        if category:
            # 带类别过滤的搜索
            cur.execute("""
                SELECT 
                    id,
                    title,
                    content,
                    embedding <=> %s::vector AS distance,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM knowledge_base
                WHERE category = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, query_embedding, category, query_embedding, top_k))
        else:
            # 全局搜索
            cur.execute("""
                SELECT 
                    id,
                    title,
                    content,
                    embedding <=> %s::vector AS distance,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM knowledge_base
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, query_embedding, query_embedding, top_k))
        
        results = cur.fetchall()
    
    conn.close()
    return results

# 使用示例
results = semantic_search("如何安装pgvector？", top_k=3)
for row in results:
    print(f"标题: {row[1]}, 相似度: {row[4]:.4f}")
```

### 6.2 BERT嵌入集成

#### 6.2.1 使用Hugging Face Transformers

```python
# 使用BERT生成嵌入
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np

# 加载模型
tokenizer = AutoTokenizer.from_pretrained('bert-base-chinese')
model = AutoModel.from_pretrained('bert-base-chinese')

def get_bert_embedding(text):
    """使用BERT生成文本嵌入"""
    # 编码文本
    inputs = tokenizer(
        text, 
        return_tensors='pt',
        truncation=True,
        max_length=512,
        padding=True
    )
    
    # 获取模型输出
    with torch.no_grad():
        outputs = model(**inputs)
    
    # 使用[CLS] token的嵌入作为句子表示
    embedding = outputs.last_hidden_state[:, 0, :].numpy()[0]
    
    # 归一化
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding.tolist()

# 示例
embedding = get_bert_embedding("这是一个测试句子")
print(f"BERT嵌入维度: {len(embedding)}")  # 768
```

#### 6.2.2 批量处理与存储

```python
from tqdm import tqdm

def batch_process_bert(documents, batch_size=32):
    """批量处理BERT嵌入"""
    all_embeddings = []
    
    for i in tqdm(range(0, len(documents), batch_size)):
        batch = documents[i:i+batch_size]
        texts = [doc['content'] for doc in batch]
        
        # 批量编码
        inputs = tokenizer(
            texts,
            return_tensors='pt',
            truncation=True,
            max_length=512,
            padding=True
        )
        
        with torch.no_grad():
            outputs = model(**inputs)
        
        # 提取嵌入
        embeddings = outputs.last_hidden_state[:, 0, :].numpy()
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        all_embeddings.extend(embeddings.tolist())
    
    return all_embeddings

# 存储到数据库
def store_bert_embeddings(documents):
    embeddings = batch_process_bert(documents)
    
    conn = psycopg2.connect(
        host="localhost",
        database="vectordb",
        user="postgres",
        password="postgres"
    )
    
    with conn.cursor() as cur:
        for doc, emb in zip(documents, embeddings):
            cur.execute("""
                INSERT INTO knowledge_base (title, content, embedding, category)
                VALUES (%s, %s, %s::vector, %s)
            """, (doc['title'], doc['content'], emb, doc.get('category', 'general')))
    
    conn.commit()
    conn.close()
```

### 6.3 LangChain集成

#### 6.3.1 LangChain向量存储

```python
# 安装依赖
# pip install langchain langchain-openai pgvector

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector

# 配置连接字符串
CONNECTION_STRING = "postgresql://postgres:postgres@localhost:5432/vectordb"

# 初始化嵌入模型
embeddings = OpenAIEmbeddings(
    model="text-embedding-ada-002",
    openai_api_key="your-api-key"
)

# 创建或加载向量存储
vectorstore = PGVector(
    connection_string=CONNECTION_STRING,
    embedding_function=embeddings,
    collection_name="documents",
    distance_strategy="cosine"  # 或 "euclidean", "max_inner_product"
)
```

#### 6.3.2 文档加载与存储

```python
from langchain.document_loaders import TextLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 加载文档
loader = DirectoryLoader('./documents', glob="**/*.txt")
documents = loader.load()

# 文档切分
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
chunks = text_splitter.split_documents(documents)

# 存储到pgvector
vectorstore.add_documents(chunks)
print(f"已存储 {len(chunks)} 个文档块")
```

#### 6.3.3 相似度搜索

```python
# 基础相似度搜索
results = vectorstore.similarity_search(
    query="什么是pgvector？",
    k=5
)

for doc in results:
    print(f"内容: {doc.page_content[:200]}...")
    print(f"元数据: {doc.metadata}")
    print("---")

# 带分数的搜索
results_with_scores = vectorstore.similarity_search_with_score(
    query="如何安装pgvector？",
    k=5
)

for doc, score in results_with_scores:
    print(f"相似度分数: {score:.4f}")
    print(f"内容: {doc.page_content[:200]}...")
    print("---")

# 最大边际相关性搜索（MMR）
# 平衡相关性和多样性
mmr_results = vectorstore.max_marginal_relevance_search(
    query="PostgreSQL优化",
    k=5,
    fetch_k=20,  # 先获取20个候选
    lambda_mult=0.5  # 多样性权重
)
```

#### 6.3.4 作为检索器使用

```python
from langchain.chains import RetrievalQA
from langchain_openai import ChatOpenAI

# 创建检索器
retriever = vectorstore.as_retriever(
    search_type="similarity",  # 或 "mmr"
    search_kwargs={"k": 5}
)

# 创建RAG链
llm = ChatOpenAI(model="gpt-4", temperature=0)
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True
)

# 执行问答
result = qa_chain.invoke({"query": "pgvector支持哪些索引类型？"})
print(f"答案: {result['result']}")
print(f"来源文档数: {len(result['source_documents'])}")
```

### 6.4 LlamaIndex集成

```python
# pip install llama-index llama-index-vector-stores-postgres

from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.embeddings.openai import OpenAIEmbedding

# 配置向量存储
vector_store = PGVectorStore.from_params(
    host="localhost",
    port=5432,
    database="vectordb",
    user="postgres",
    password="postgres",
    table_name="llama_index_docs",
    embed_dim=1536  # OpenAI嵌入维度
)

# 加载文档
documents = SimpleDirectoryReader("./documents").load_data()

# 创建索引
index = VectorStoreIndex.from_documents(
    documents,
    vector_store=vector_store,
    embed_model=OpenAIEmbedding()
)

# 创建查询引擎
query_engine = index.as_query_engine()

# 查询
response = query_engine.query("pgvector的主要特性是什么？")
print(response)
```

---


### 6.1 OpenAI Embeddings集成

OpenAI提供了强大的文本嵌入模型，可以轻松集成到pgvector中。

**安装依赖：**

```bash
pip install openai psycopg2-binary pgvector
```

**完整集成代码：**

```python
import os
import openai
import psycopg2
from pgvector.psycopg2 import register_vector
import numpy as np

# 配置OpenAI API
openai.api_key = os.getenv("OPENAI_API_KEY")

class OpenAIPGVector:
    def __init__(self, db_config):
        self.conn = psycopg2.connect(**db_config)
        register_vector(self.conn)
        self.cursor = self.conn.cursor()
    
    def get_embedding(self, text, model="text-embedding-3-small"):
        """获取文本的OpenAI嵌入向量"""
        response = openai.embeddings.create(
            model=model,
            input=text
        )
        return np.array(response.data[0].embedding, dtype=np.float32)
    
    def add_document(self, title, content, metadata=None):
        """添加文档及其嵌入"""
        # 组合标题和内容生成嵌入
        full_text = f"{title}\n{content}"
        embedding = self.get_embedding(full_text)
        
        self.cursor.execute("""
            INSERT INTO documents (title, content, metadata, embedding)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (title, content, metadata or {}, embedding))
        
        self.conn.commit()
        return self.cursor.fetchone()[0]
    
    def search(self, query, top_k=5):
        """语义搜索"""
        query_embedding = self.get_embedding(query)
        
        self.cursor.execute("""
            SELECT id, title, content,
                   embedding <=> %s AS distance
            FROM documents
            ORDER BY embedding <=> %s
            LIMIT %s
        """, (query_embedding, query_embedding, top_k))
        
        return [
            {
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'distance': row[3]
            }
            for row in self.cursor.fetchall()
        ]
    
    def close(self):
        self.cursor.close()
        self.conn.close()

# 使用示例
if __name__ == "__main__":
    db_config = {
        "host": "localhost",
        "database": "vectordb",
        "user": "postgres",
        "password": "your_password"
    }
    
    vector_db = OpenAIPGVector(db_config)
    
    # 添加文档
    vector_db.add_document(
        "PostgreSQL简介",
        "PostgreSQL是一个强大的开源关系型数据库...",
        {"category": "database"}
    )
    
    # 搜索
    results = vector_db.search("什么是PostgreSQL数据库", top_k=3)
    for result in results:
        print(f"{result['title']} (距离: {result['distance']:.4f})")
    
    vector_db.close()
```


### 6.2 Hugging Face模型集成

使用开源模型在本地生成嵌入，无需调用外部API。

**安装依赖：**

```bash
pip install transformers torch psycopg2-binary pgvector
```

**本地嵌入模型集成：**

```python
from transformers import AutoTokenizer, AutoModel
import torch
import psycopg2
from pgvector.psycopg2 import register_vector
import numpy as np

class HuggingFacePGVector:
    def __init__(self, db_config, model_name="sentence-transformers/all-MiniLM-L6-v2"):
        self.conn = psycopg2.connect(**db_config)
        register_vector(self.conn)
        self.cursor = self.conn.cursor()
        
        # 加载本地模型
        print(f"加载模型: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()
        
        # 获取嵌入维度
        self.embedding_dim = self.model.config.hidden_size
    
    def get_embedding(self, text):
        """使用Hugging Face模型生成嵌入"""
        # 分词
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True
        )
        
        # 生成嵌入
        with torch.no_grad():
            outputs = self.model(**inputs)
            # 使用[CLS] token的嵌入或平均池化
            embedding = outputs.last_hidden_state.mean(dim=1).squeeze()
        
        return embedding.numpy().astype(np.float32)
    
    def add_document(self, title, content, metadata=None):
        """添加文档"""
        full_text = f"{title}\n{content}"
        embedding = self.get_embedding(full_text)
        
        self.cursor.execute("""
            INSERT INTO documents (title, content, metadata, embedding)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (title, content, metadata or {}, embedding))
        
        self.conn.commit()
        return self.cursor.fetchone()[0]
    
    def search(self, query, top_k=5):
        """搜索相似文档"""
        query_embedding = self.get_embedding(query)
        
        self.cursor.execute("""
            SELECT id, title, content,
                   embedding <=> %s AS distance
            FROM documents
            ORDER BY embedding <=> %s
            LIMIT %s
        """, (query_embedding, query_embedding, top_k))
        
        return [
            {
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'distance': row[3]
            }
            for row in self.cursor.fetchall()
        ]
    
    def close(self):
        self.cursor.close()
        self.conn.close()

# 使用示例
if __name__ == "__main__":
    db_config = {
        "host": "localhost",
        "database": "vectordb",
        "user": "postgres",
        "password": "your_password"
    }
    
    # 使用轻量级模型
    vector_db = HuggingFacePGVector(
        db_config,
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # 添加文档
    vector_db.add_document(
        "机器学习基础",
        "机器学习是人工智能的一个分支...",
        {"category": "ai"}
    )
    
    # 搜索
    results = vector_db.search("人工智能和机器学习的关系", top_k=3)
    for result in results:
        print(f"{result['title']} (距离: {result['distance']:.4f})")
    
    vector_db.close()
```


### 6.3 LangChain集成

LangChain提供了PGVector封装类，简化了向量存储和检索。

**安装依赖：**

```bash
pip install langchain langchain-openai pgvector psycopg2-binary
```

**LangChain PGVector使用：**

```python
from langchain_community.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
import os

# 配置
CONNECTION_STRING = "postgresql://postgres:password@localhost:5432/vectordb"
COLLECTION_NAME = "langchain_documents"

# 初始化嵌入模型
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

# 方式1: 从文档创建向量存储
documents = [
    Document(
        page_content="PostgreSQL是一个强大的开源关系型数据库管理系统",
        metadata={"source": "intro", "category": "database"}
    ),
    Document(
        page_content="pgvector扩展为PostgreSQL添加了向量相似性搜索功能",
        metadata={"source": "pgvector", "category": "database"}
    ),
    Document(
        page_content="向量数据库用于存储和检索高维向量数据",
        metadata={"source": "vector_db", "category": "ai"}
    ),
]

# 创建向量存储（自动创建表和索引）
vector_store = PGVector.from_documents(
    documents=documents,
    embedding=embeddings,
    collection_name=COLLECTION_NAME,
    connection_string=CONNECTION_STRING,
    distance_strategy="cosine",  # 或 "euclidean", "max_inner_product"
)

# 方式2: 连接到现有向量存储
vector_store = PGVector(
    connection_string=CONNECTION_STRING,
    embedding_function=embeddings,
    collection_name=COLLECTION_NAME,
    distance_strategy="cosine",
)

# 添加更多文档
new_documents = [
    Document(
        page_content="HNSW索引提供高效的近似最近邻搜索",
        metadata={"source": "hnsw", "category": "database"}
    ),
]
vector_store.add_documents(new_documents)

# 相似性搜索
results = vector_store.similarity_search(
    query="什么是pgvector",
    k=3,
    filter={"category": "database"}  # 可选的元数据过滤
)

print("相似性搜索结果:")
for doc in results:
    print(f"- {doc.page_content}")
    print(f"  元数据: {doc.metadata}")

# 带分数的相似性搜索
results_with_score = vector_store.similarity_search_with_score(
    query="向量数据库的功能",
    k=3
)

print("\n带分数的搜索结果:")
for doc, score in results_with_score:
    print(f"- {doc.page_content}")
    print(f"  相似度分数: {score:.4f}")

# 最大边际相关性搜索（MMR）- 平衡相关性和多样性
mmr_results = vector_store.max_marginal_relevance_search(
    query="数据库技术",
    k=3,
    fetch_k=10,  # 先获取10个，然后选择3个最多样化的
    lambda_mult=0.5  # 多样性权重
)

print("\nMMR搜索结果:")
for doc in mmr_results:
    print(f"- {doc.page_content}")
```

---


## 第7章 Spring AI与pgvector集成详解

### 7.1 项目依赖配置

#### 7.1.1 Maven依赖

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
    </parent>
    
    <groupId>com.example</groupId>
    <artifactId>pgvector-spring-demo</artifactId>
    <version>1.0.0</version>
    
    <properties>
        <java.version>17</java.version>
        <spring-ai.version>0.8.0</spring-ai.version>
    </properties>
    
    <dependencies>
        <!-- Spring Boot Starter -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <!-- Spring AI -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-openai-spring-boot-starter</artifactId>
        </dependency>
        
        <!-- Spring AI pgvector -->
        <dependency>
            <groupId>org.springframework.ai</groupId>
            <artifactId>spring-ai-pgvector-store-spring-boot-starter</artifactId>
        </dependency>
        
        <!-- PostgreSQL JDBC -->
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
        </dependency>
        
        <!-- Spring Data JDBC -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-jdbc</artifactId>
        </dependency>
        
        <!-- Test -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
    
    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.ai</groupId>
                <artifactId>spring-ai-bom</artifactId>
                <version>${spring-ai.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>
</project>
```

#### 7.1.2 Gradle依赖

```groovy
plugins {
    id 'java'
    id 'org.springframework.boot' version '3.2.0'
}

java {
    sourceCompatibility = '17'
}

repositories {
    mavenCentral()
    maven { url 'https://repo.spring.io/milestone' }
}

ext {
    set('springAiVersion', "0.8.0")
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.ai:spring-ai-openai-spring-boot-starter'
    implementation 'org.springframework.ai:spring-ai-pgvector-store-spring-boot-starter'
    implementation 'org.postgresql:postgresql'
    implementation 'org.springframework.boot:spring-boot-starter-jdbc'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}

dependencyManagement {
    imports {
        mavenBom "org.springframework.ai:spring-ai-bom:${springAiVersion}"
    }
}
```

### 7.2 配置文件

#### 7.2.1 application.yml

```yaml
spring:
  # 数据源配置
  datasource:
    url: jdbc:postgresql://localhost:5432/vectordb
    username: postgres
    password: postgres
    driver-class-name: org.postgresql.Driver
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5
      connection-timeout: 30000

  # OpenAI配置
  ai:
    openai:
      api-key: ${OPENAI_API_KEY}
      embedding:
        options:
          model: text-embedding-ada-002

    # pgvector配置
    vectorstore:
      pgvector:
        index-type: HNSW
        distance-type: COSINE_DISTANCE
        dimensions: 1536
        initialize-schema: true
        max-document-batch-size: 10000
        remove-existing-vector-store-table: false

# 日志配置
logging:
  level:
    org.springframework.ai: DEBUG
    org.springframework.jdbc: DEBUG
```

#### 7.2.2 application.properties

```properties
# 数据源
spring.datasource.url=jdbc:postgresql://localhost:5432/vectordb
spring.datasource.username=postgres
spring.datasource.password=postgres

# OpenAI
spring.ai.openai.api-key=${OPENAI_API_KEY}
spring.ai.openai.embedding.options.model=text-embedding-ada-002

# pgvector
spring.ai.vectorstore.pgvector.index-type=HNSW
spring.ai.vectorstore.pgvector.distance-type=COSINE_DISTANCE
spring.ai.vectorstore.pgvector.dimensions=1536
spring.ai.vectorstore.pgvector.initialize-schema=true
```

### 7.3 核心代码实现

#### 7.3.1 向量存储配置类

```java
package com.example.pgvector.config;

import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.vectorstore.PgVectorStore;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

@Configuration
public class VectorStoreConfig {

    /**
     * 配置PgVectorStore
     */
    @Bean
    public PgVectorStore pgVectorStore(
            JdbcTemplate jdbcTemplate,
            EmbeddingModel embeddingModel) {
        
        return PgVectorStore.builder(jdbcTemplate, embeddingModel)
                .dimensions(1536)
                .distanceType(PgVectorStore.PgDistanceType.COSINE_DISTANCE)
                .indexType(PgVectorStore.PgIndexType.HNSW)
                .initializeSchema(true)
                .maxDocumentBatchSize(10000)
                .build();
    }
}
```

#### 7.3.2 文档服务类

```java
package com.example.pgvector.service;

import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
public class DocumentService {

    private final VectorStore vectorStore;

    @Autowired
    public DocumentService(VectorStore vectorStore) {
        this.vectorStore = vectorStore;
    }

    /**
     * 添加单个文档
     */
    public void addDocument(String content) {
        Document document = new Document(content);
        vectorStore.add(List.of(document));
    }

    /**
     * 添加带元数据的文档
     */
    public void addDocument(String content, Map<String, Object> metadata) {
        Document document = new Document(content, metadata);
        vectorStore.add(List.of(document));
    }

    /**
     * 批量添加文档
     */
    public void addDocuments(List<String> contents) {
        List<Document> documents = contents.stream()
                .map(Document::new)
                .collect(Collectors.toList());
        vectorStore.add(documents);
    }

    /**
     * 相似度搜索
     */
    public List<Document> search(String query, int topK) {
        SearchRequest request = SearchRequest.query(query)
                .withTopK(topK);
        return vectorStore.similaritySearch(request);
    }

    /**
     * 带过滤条件的搜索
     */
    public List<Document> searchWithFilter(
            String query, 
            int topK, 
            Map<String, Object> filter) {
        
        SearchRequest request = SearchRequest.query(query)
                .withTopK(topK)
                .withFilterExpression(buildFilterExpression(filter));
        
        return vectorStore.similaritySearch(request);
    }

    /**
     * 构建过滤表达式
     */
    private String buildFilterExpression(Map<String, Object> filter) {
        return filter.entrySet().stream()
                .map(entry -> {
                    String key = entry.getKey();
                    Object value = entry.getValue();
                    if (value instanceof String) {
                        return key + " == '" + value + "'";
                    }
                    return key + " == " + value;
                })
                .collect(Collectors.joining(" && "));
    }
}
```

#### 7.3.3 RAG服务类

```java
package com.example.pgvector.service;

import org.springframework.ai.chat.ChatClient;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.SystemMessage;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
public class RAGService {

    private final VectorStore vectorStore;
    private final ChatClient chatClient;

    @Autowired
    public RAGService(VectorStore vectorStore, ChatClient chatClient) {
        this.vectorStore = vectorStore;
        this.chatClient = chatClient;
    }

    /**
     * RAG问答
     */
    public String answerQuestion(String question, int topK) {
        // 1. 检索相关文档
        List<Document> relevantDocs = vectorStore.similaritySearch(
                org.springframework.ai.vectorstore.SearchRequest
                        .query(question)
                        .withTopK(topK)
        );

        // 2. 构建上下文
        String context = relevantDocs.stream()
                .map(Document::getContent)
                .collect(Collectors.joining("\n\n"));

        // 3. 构建系统提示
        String systemPrompt = """
            你是一个专业的技术助手。请基于以下上下文信息回答用户的问题。
            如果上下文中没有相关信息，请明确说明。
            
            上下文信息：
            %s
            """.formatted(context);

        // 4. 调用大模型
        List<Message> messages = List.of(
                new SystemMessage(systemPrompt),
                new UserMessage(question)
        );

        return chatClient.call(new Prompt(messages))
                .getResult()
                .getOutput()
                .getContent();
    }

    /**
     * 带过滤条件的RAG问答
     */
    public String answerQuestionWithFilter(
            String question, 
            int topK,
            String category) {
        
        // 构建过滤条件
        String filterExpr = "category == '" + category + "'";
        
        // 检索相关文档
        List<Document> relevantDocs = vectorStore.similaritySearch(
                org.springframework.ai.vectorstore.SearchRequest
                        .query(question)
                        .withTopK(topK)
                        .withFilterExpression(filterExpr)
        );

        String context = relevantDocs.stream()
                .map(Document::getContent)
                .collect(Collectors.joining("\n\n"));

        String systemPrompt = """
            你是一个专业的技术助手。请基于以下上下文信息回答用户的问题。
            如果上下文中没有相关信息，请明确说明。
            
            上下文信息：
            %s
            """.formatted(context);

        List<Message> messages = List.of(
                new SystemMessage(systemPrompt),
                new UserMessage(question)
        );

        return chatClient.call(new Prompt(messages))
                .getResult()
                .getOutput()
                .getContent();
    }
}
```

#### 7.3.4 REST API控制器

```java
package com.example.pgvector.controller;

import com.example.pgvector.service.DocumentService;
import com.example.pgvector.service.RAGService;
import org.springframework.ai.document.Document;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class VectorController {

    private final DocumentService documentService;
    private final RAGService ragService;

    @Autowired
    public VectorController(DocumentService documentService, RAGService ragService) {
        this.documentService = documentService;
        this.ragService = ragService;
    }

    /**
     * 添加文档
     */
    @PostMapping("/documents")
    public ResponseEntity<String> addDocument(
            @RequestBody Map<String, Object> request) {
        
        String content = (String) request.get("content");
        @SuppressWarnings("unchecked")
        Map<String, Object> metadata = (Map<String, Object>) request.getOrDefault(
                "metadata", new HashMap<>());
        
        documentService.addDocument(content, metadata);
        return ResponseEntity.ok("Document added successfully");
    }

    /**
     * 搜索相似文档
     */
    @GetMapping("/search")
    public ResponseEntity<List<Document>> search(
            @RequestParam String query,
            @RequestParam(defaultValue = "5") int topK) {
        
        List<Document> results = documentService.search(query, topK);
        return ResponseEntity.ok(results);
    }

    /**
     * RAG问答
     */
    @PostMapping("/rag/ask")
    public ResponseEntity<Map<String, Object>> askQuestion(
            @RequestBody Map<String, Object> request) {
        
        String question = (String) request.get("question");
        int topK = (int) request.getOrDefault("topK", 5);
        
        String answer = ragService.answerQuestion(question, topK);
        
        Map<String, Object> response = new HashMap<>();
        response.put("question", question);
        response.put("answer", answer);
        
        return ResponseEntity.ok(response);
    }
}
```

### 7.4 高级配置

#### 7.4.1 自定义向量存储表结构

```java
package com.example.pgvector.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;

import javax.sql.DataSource;

@Configuration
public class DatabaseConfig {

    @Bean
    public JdbcTemplate jdbcTemplate(DataSource dataSource) {
        return new JdbcTemplate(dataSource);
    }

    /**
     * 自定义初始化schema
     */
    @Bean
    public ResourceDatabasePopulator databasePopulator(
            ResourceLoader resourceLoader) {
        
        ResourceDatabasePopulator populator = new ResourceDatabasePopulator();
        populator.addScript(resourceLoader.getResource(
                "classpath:schema-custom.sql"));
        return populator;
    }
}
```

#### 7.4.2 自定义schema.sql

```sql
-- schema-custom.sql
-- 自定义向量存储表结构

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 自定义向量表
CREATE TABLE IF NOT EXISTS custom_vector_store (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    metadata JSONB DEFAULT '{}',
    category VARCHAR(100),
    source VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建HNSW索引
CREATE INDEX IF NOT EXISTS idx_custom_vector_embedding 
ON custom_vector_store 
USING hnsw (embedding vector_cosine_ops);

-- 创建元数据GIN索引
CREATE INDEX IF NOT EXISTS idx_custom_vector_metadata 
ON custom_vector_store 
USING GIN(metadata);

-- 创建类别索引
CREATE INDEX IF NOT EXISTS idx_custom_vector_category 
ON custom_vector_store(category);

-- 更新时间触发器
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_custom_vector_updated_at ON custom_vector_store;
CREATE TRIGGER update_custom_vector_updated_at
    BEFORE UPDATE ON custom_vector_store
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### 7.5 测试示例

```java
package com.example.pgvector;

import com.example.pgvector.service.DocumentService;
import org.junit.jupiter.api.Test;
import org.springframework.ai.document.Document;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
class PgvectorApplicationTests {

    @Autowired
    private DocumentService documentService;

    @Test
    void testAddAndSearch() {
        // 添加测试文档
        Map<String, Object> metadata = new HashMap<>();
        metadata.put("category", "test");
        metadata.put("source", "unit-test");
        
        documentService.addDocument(
                "pgvector是PostgreSQL的向量扩展，支持相似度搜索", 
                metadata
        );
        
        // 搜索
        List<Document> results = documentService.search("向量数据库", 5);
        
        // 验证
        assertFalse(results.isEmpty());
        assertTrue(results.get(0).getContent().contains("pgvector"));
    }

    @Test
    void testSearchWithFilter() {
        // 添加带过滤条件的文档
        Map<String, Object> metadata1 = new HashMap<>();
        metadata1.put("category", "database");
        documentService.addDocument("PostgreSQL是一个关系型数据库", metadata1);
        
        Map<String, Object> metadata2 = new HashMap<>();
        metadata2.put("category", "ai");
        documentService.addDocument("机器学习是人工智能的分支", metadata2);
        
        // 带过滤搜索
        Map<String, Object> filter = new HashMap<>();
        filter.put("category", "database");
        
        List<Document> results = documentService.searchWithFilter(
                "数据库技术", 5, filter);
        
        // 验证
        assertFalse(results.isEmpty());
        results.forEach(doc -> 
            assertEquals("database", doc.getMetadata().get("category"))
        );
    }
}
```

---

## 第8章 实际应用场景

## 7. RAG系统实现

### 7.1 RAG架构设计

RAG（Retrieval-Augmented Generation，检索增强生成）是一种将向量检索与大型语言模型结合的架构。

**RAG系统架构图：**

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAG系统架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   文档输入    │───>│  文本分割    │───>│  嵌入生成    │      │
│  │  (PDF/TXT等) │    │  (Chunking)  │    │ (Embeddings) │      │
│  └──────────────┘    └──────────────┘    └──────┬───────┘      │
│                                                  │              │
│                                                  ▼              │
│                                         ┌──────────────┐       │
│                                         │   pgvector   │       │
│                                         │  (向量存储)   │       │
│                                         └──────┬───────┘       │
│                                                │                │
│  ┌─────────────────────────────────────────────┘                │
│  │                                                              │
│  ▼                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   用户查询    │───>│  向量检索    │───>│  上下文构建  │      │
│  │   (Query)    │    │ (Similarity) │    │  (Context)   │      │
│  └──────────────┘    └──────────────┘    └──────┬───────┘      │
│                                                  │              │
│                                                  ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   最终输出    │<───│  LLM生成    │<───│  Prompt构建  │      │
│  │  (Response)  │    │ (Generation) │    │   (Prompt)   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**核心组件：**

| 组件 | 功能 | 技术选型 |
|------|------|----------|
| 文档处理 | 加载和解析文档 | LangChain Document Loaders |
| 文本分割 | 将文档切分为chunks | RecursiveCharacterTextSplitter |
| 嵌入模型 | 生成文本向量 | OpenAI / Hugging Face |
| 向量存储 | 存储和检索向量 | pgvector |
| LLM | 生成回答 | GPT-4 / Claude / 本地模型 |

### 7.2 完整实现代码

**完整的RAG系统实现：**

```python
import os
from typing import List, Dict, Any
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import PGVector
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate

class RAGSystem:
    """基于pgvector的RAG系统"""
    
    def __init__(
        self,
        connection_string: str,
        collection_name: str = "rag_documents",
        embedding_model: str = "text-embedding-3-small",
        llm_model: str = "gpt-4"
    ):
        self.connection_string = connection_string
        self.collection_name = collection_name
        
        # 初始化嵌入模型
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # 初始化LLM
        self.llm = ChatOpenAI(
            model=llm_model,
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # 初始化向量存储
        self.vector_store = PGVector(
            connection_string=connection_string,
            embedding_function=self.embeddings,
            collection_name=collection_name,
            distance_strategy="cosine",
        )
        
        # 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # 自定义Prompt模板
        self.prompt_template = PromptTemplate(
            template="""基于以下上下文信息回答问题。如果上下文不包含答案，请说明"根据提供的信息无法回答"。

上下文：
{context}

问题：{question}

请提供详细且准确的回答：""",
            input_variables=["context", "question"]
        )
    
    def load_documents(self, file_paths: List[str]) -> List[Any]:
        """加载文档"""
        documents = []
        for file_path in file_paths:
            if file_path.endswith('.pdf'):
                loader = PyPDFLoader(file_path)
            else:
                loader = TextLoader(file_path, encoding='utf-8')
            documents.extend(loader.load())
        return documents
    
    def process_and_store(
        self,
        file_paths: List[str],
        metadata: Dict[str, Any] = None
    ):
        """处理文档并存储到向量数据库"""
        # 加载文档
        documents = self.load_documents(file_paths)
        
        # 添加元数据
        if metadata:
            for doc in documents:
                doc.metadata.update(metadata)
        
        # 分割文本
        chunks = self.text_splitter.split_documents(documents)
        print(f"文档分割为 {len(chunks)} 个chunks")
        
        # 存储到向量数据库
        self.vector_store.add_documents(chunks)
        print(f"已存储到向量数据库")
    
    def query(
        self,
        question: str,
        top_k: int = 5,
        filter_dict: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        执行RAG查询
        
        Args:
            question: 用户问题
            top_k: 检索的文档数量
            filter_dict: 元数据过滤条件
        
        Returns:
            包含回答和检索到的文档的字典
        """
        # 检索相关文档
        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": top_k,
                "filter": filter_dict
            }
        )
        
        # 创建RAG链
        qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": self.prompt_template}
        )
        
        # 执行查询
        result = qa_chain.invoke({"query": question})
        
        return {
            "question": question,
            "answer": result["result"],
            "source_documents": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                }
                for doc in result["source_documents"]
            ]
        }
    
    def similarity_search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """纯相似性搜索（不调用LLM）"""
        results = self.vector_store.similarity_search_with_score(query, k=top_k)
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": score
            }
            for doc, score in results
        ]

# 使用示例
if __name__ == "__main__":
    # 配置
    CONNECTION_STRING = "postgresql://postgres:password@localhost:5432/vectordb"
    
    # 初始化RAG系统
    rag = RAGSystem(
        connection_string=CONNECTION_STRING,
        collection_name="knowledge_base"
    )
    
    # 处理并存储文档
    rag.process_and_store(
        file_paths=["document1.pdf", "document2.txt"],
        metadata={"source": "internal_docs", "department": "engineering"}
    )
    
    # 执行RAG查询
    result = rag.query(
        question="pgvector的主要功能是什么？",
        top_k=5
    )
    
    print("问题:", result["question"])
    print("\n回答:", result["answer"])
    print("\n参考文档:")
    for i, doc in enumerate(result["source_documents"], 1):
        print(f"{i}. {doc['content'][:100]}...")
```

### 7.3 优化策略

**1. 文本分割优化：**

```python
# 针对不同文档类型使用不同的分割策略

# 代码文档
code_splitter = RecursiveCharacterTextSplitter.from_language(
    language="python",
    chunk_size=1000,
    chunk_overlap=200,
)

# Markdown文档
markdown_splitter = RecursiveCharacterTextSplitter.from_language(
    language="markdown",
    chunk_size=1000,
    chunk_overlap=200,
)

# 自定义分隔符
custom_splitter = RecursiveCharacterTextSplitter(
    separators=["\n\n", "\n", "。", "，", " ", ""],
    chunk_size=500,
    chunk_overlap=100,
)
```

**2. 混合搜索策略：**

```python
from langchain.retrievers import BM25Retriever, EnsembleRetriever

def create_hybrid_retriever(vector_store, documents):
    """创建混合检索器（向量搜索 + 关键词搜索）"""
    # 向量检索器
    vector_retriever = vector_store.as_retriever(
        search_kwargs={"k": 5}
    )
    
    # BM25关键词检索器
    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = 5
    
    # 组合检索器
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.3, 0.7]  # 权重可调
    )
    
    return ensemble_retriever
```

**3. 重排序优化：**

```python
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

def create_reranker_retriever(base_retriever, llm):
    """创建带重排序的检索器"""
    compressor = LLMChainExtractor.from_llm(llm)
    
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever
    )
    
    return compression_retriever
```

---


### 8.1 RAG（检索增强生成）系统

RAG是将外部知识检索与大语言模型结合的架构，pgvector在其中扮演知识库的角色。

#### 8.1.1 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAG系统架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   用户查询    │───▶│  查询向量化   │───▶│  pgvector检索 │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                   │             │
│                                                   ▼             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   生成回答    │◀───│   LLM推理    │◀───│  上下文构建   │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 8.1.2 知识库表设计

```sql
-- RAG知识库表
CREATE TABLE rag_knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- 文档内容
    title VARCHAR(500),
    content TEXT NOT NULL,
    content_chunk TEXT,  -- 切分后的内容块
    chunk_index INT,     -- 块索引
    
    -- 向量嵌入
    embedding vector(1536),
    
    -- 文档元数据
    doc_id VARCHAR(100),          -- 原始文档ID
    doc_type VARCHAR(50),         -- 文档类型：pdf, doc, web
    source_url VARCHAR(1000),     -- 来源URL
    
    -- 分类信息
    category VARCHAR(100),
    subcategory VARCHAR(100),
    tags TEXT[],
    
    -- 权限控制
    access_level VARCHAR(20) DEFAULT 'public',
    owner_id VARCHAR(100),
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 额外元数据
    metadata JSONB DEFAULT '{}'
);

-- 创建索引
CREATE INDEX idx_rag_kb_embedding ON rag_knowledge_base 
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_rag_kb_category ON rag_knowledge_base(category);
CREATE INDEX idx_rag_kb_doc_id ON rag_knowledge_base(doc_id);
CREATE INDEX idx_rag_kb_tags ON rag_knowledge_base USING GIN(tags);
CREATE INDEX idx_rag_kb_metadata ON rag_knowledge_base USING GIN(metadata);
```

#### 8.1.3 文档处理流程

```python
# document_processor.py
import hashlib
from typing import List, Dict
import openai
import psycopg2
from langchain.text_splitter import RecursiveCharacterTextSplitter

class DocumentProcessor:
    def __init__(self, db_config: Dict, openai_key: str):
        self.db_config = db_config
        openai.api_key = openai_key
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", "。", "；", " "]
        )
    
    def process_document(self, doc: Dict) -> List[Dict]:
        """处理单个文档，返回切分后的块"""
        # 生成文档ID
        doc_id = hashlib.md5(
            doc['source_url'].encode()
        ).hexdigest()[:16]
        
        # 切分文本
        chunks = self.text_splitter.split_text(doc['content'])
        
        # 为每个块生成嵌入
        processed_chunks = []
        for i, chunk in enumerate(chunks):
            embedding = self._generate_embedding(chunk)
            
            processed_chunks.append({
                'doc_id': doc_id,
                'title': doc.get('title', ''),
                'content': doc['content'],
                'content_chunk': chunk,
                'chunk_index': i,
                'embedding': embedding,
                'doc_type': doc.get('doc_type', 'unknown'),
                'source_url': doc.get('source_url', ''),
                'category': doc.get('category', 'general'),
                'tags': doc.get('tags', [])
            })
        
        return processed_chunks
    
    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入"""
        response = openai.Embedding.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response['data'][0]['embedding']
    
    def save_to_database(self, chunks: List[Dict]):
        """保存到数据库"""
        conn = psycopg2.connect(**self.db_config)
        
        with conn.cursor() as cur:
            for chunk in chunks:
                cur.execute("""
                    INSERT INTO rag_knowledge_base 
                    (doc_id, title, content, content_chunk, chunk_index,
                     embedding, doc_type, source_url, category, tags)
                    VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s)
                    ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                        content_chunk = EXCLUDED.content_chunk,
                        embedding = EXCLUDED.embedding,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    chunk['doc_id'],
                    chunk['title'],
                    chunk['content'],
                    chunk['content_chunk'],
                    chunk['chunk_index'],
                    chunk['embedding'],
                    chunk['doc_type'],
                    chunk['source_url'],
                    chunk['category'],
                    chunk['tags']
                ))
        
        conn.commit()
        conn.close()
```

#### 8.1.4 RAG查询服务

```python
# rag_service.py
import openai
import psycopg2
from typing import List, Dict, Optional

class RAGService:
    def __init__(self, db_config: Dict, openai_key: str):
        self.db_config = db_config
        openai.api_key = openai_key
    
    def retrieve_context(
        self, 
        query: str, 
        top_k: int = 5,
        category: Optional[str] = None,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        """检索相关上下文"""
        # 生成查询嵌入
        query_embedding = self._generate_embedding(query)
        
        conn = psycopg2.connect(**self.db_config)
        
        with conn.cursor() as cur:
            if category:
                cur.execute("""
                    SELECT 
                        id,
                        title,
                        content_chunk,
                        source_url,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM rag_knowledge_base
                    WHERE category = %s
                      AND 1 - (embedding <=> %s::vector) > %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (query_embedding, category, query_embedding, 
                      min_similarity, query_embedding, top_k))
            else:
                cur.execute("""
                    SELECT 
                        id,
                        title,
                        content_chunk,
                        source_url,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM rag_knowledge_base
                    WHERE 1 - (embedding <=> %s::vector) > %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (query_embedding, query_embedding, 
                      min_similarity, query_embedding, top_k))
            
            results = cur.fetchall()
        
        conn.close()
        
        return [
            {
                'id': row[0],
                'title': row[1],
                'content': row[2],
                'source': row[3],
                'similarity': row[4]
            }
            for row in results
        ]
    
    def generate_answer(
        self, 
        query: str, 
        context: List[Dict],
        model: str = "gpt-4"
    ) -> Dict:
        """生成答案"""
        # 构建上下文
        context_text = "\n\n".join([
            f"[来源: {ctx['source']}, 相似度: {ctx['similarity']:.2f}]\n{ctx['content']}"
            for ctx in context
        ])
        
        # 构建提示
        system_prompt = f"""你是一个专业的AI助手。请基于以下上下文信息回答用户的问题。
如果上下文中没有足够信息，请明确说明。

上下文信息：
{context_text}

请用中文回答，并在回答末尾列出参考来源。"""

        # 调用LLM
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return {
            'answer': response['choices'][0]['message']['content'],
            'sources': [ctx['source'] for ctx in context],
            'context_used': len(context)
        }
    
    def query(self, query: str, **kwargs) -> Dict:
        """完整的RAG查询流程"""
        context = self.retrieve_context(query, **kwargs)
        
        if not context:
            return {
                'answer': '抱歉，未找到相关信息。',
                'sources': [],
                'context_used': 0
            }
        
        return self.generate_answer(query, context)
```

### 8.2 语义搜索系统

#### 8.2.1 电商商品搜索

```sql
-- 商品向量表
CREATE TABLE product_embeddings (
    product_id VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(500),
    description TEXT,
    category_path VARCHAR(500),
    price DECIMAL(10, 2),
    
    -- 多模态嵌入
    text_embedding vector(768),    -- 文本描述嵌入
    image_embedding vector(512),   -- 图片嵌入
    combined_embedding vector(768), -- 融合嵌入
    
    -- 商品属性
    attributes JSONB,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_product_text_embedding ON product_embeddings 
USING hnsw (text_embedding vector_cosine_ops);

CREATE INDEX idx_product_combined_embedding ON product_embeddings 
USING hnsw (combined_embedding vector_cosine_ops);

CREATE INDEX idx_product_category ON product_embeddings(category_path);
```

```python
# semantic_search.py
class SemanticProductSearch:
    def __init__(self, db_config: Dict):
        self.db_config = db_config
    
    def search(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        top_k: int = 20
    ) -> List[Dict]:
        """语义商品搜索"""
        # 生成查询嵌入
        query_embedding = self._generate_embedding(query)
        
        conn = psycopg2.connect(**self.db_config)
        
        # 构建查询条件
        conditions = ["1 - (combined_embedding <=> %s::vector) > 0.6"]
        params = [query_embedding]
        
        if category:
            conditions.append("category_path LIKE %s")
            params.append(f"%{category}%")
        
        if min_price:
            conditions.append("price >= %s")
            params.append(min_price)
        
        if max_price:
            conditions.append("price <= %s")
            params.append(max_price)
        
        where_clause = " AND ".join(conditions)
        params.extend([query_embedding, top_k])
        
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT 
                    product_id,
                    product_name,
                    description,
                    price,
                    category_path,
                    1 - (combined_embedding <=> %s::vector) AS similarity
                FROM product_embeddings
                WHERE {where_clause}
                ORDER BY combined_embedding <=> %s::vector
                LIMIT %s
            """, params)
            
            results = cur.fetchall()
        
        conn.close()
        
        return [
            {
                'product_id': row[0],
                'name': row[1],
                'description': row[2][:200],
                'price': row[3],
                'category': row[4],
                'similarity': row[5]
            }
            for row in results
        ]
    
    def hybrid_search(
        self,
        query: str,
        keywords: Optional[List[str]] = None,
        top_k: int = 20
    ) -> List[Dict]:
        """混合搜索：语义搜索 + 关键词匹配"""
        # 语义搜索结果
        semantic_results = self.search(query, top_k=top_k * 2)
        
        if not keywords:
            return semantic_results[:top_k]
        
        # 关键词匹配评分
        keyword_pattern = '|'.join(keywords)
        
        conn = psycopg2.connect(**self.db_config)
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    product_id,
                    CASE 
                        WHEN product_name ~* %s THEN 0.3
                        WHEN description ~* %s THEN 0.2
                        ELSE 0
                    END AS keyword_score
                FROM product_embeddings
                WHERE product_name ~* %s OR description ~* %s
            """, (keyword_pattern, keyword_pattern, 
                  keyword_pattern, keyword_pattern))
            
            keyword_scores = {row[0]: row[1] for row in cur.fetchall()}
        
        conn.close()
        
        # 融合评分
        for result in semantic_results:
            pid = result['product_id']
            semantic_score = result['similarity']
            keyword_score = keyword_scores.get(pid, 0)
            result['hybrid_score'] = semantic_score * 0.7 + keyword_score * 0.3
        
        # 按融合评分排序
        semantic_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        
        return semantic_results[:top_k]
```

### 8.3 推荐系统

#### 8.3.1 用户-物品协同过滤

```sql
-- 用户行为表
CREATE TABLE user_interactions (
    user_id VARCHAR(50),
    item_id VARCHAR(50),
    interaction_type VARCHAR(20),  -- view, click, purchase, like
    score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, item_id, interaction_type)
);

-- 用户画像向量表
CREATE TABLE user_profiles (
    user_id VARCHAR(50) PRIMARY KEY,
    preference_vector vector(256),
    interaction_count INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 物品向量表
CREATE TABLE item_vectors (
    item_id VARCHAR(50) PRIMARY KEY,
    item_vector vector(256),
    category VARCHAR(100),
    popularity_score FLOAT DEFAULT 0
);

-- 创建索引
CREATE INDEX idx_user_profile_vector ON user_profiles 
USING hnsw (preference_vector vector_cosine_ops);

CREATE INDEX idx_item_vector ON item_vectors 
USING hnsw (item_vector vector_cosine_ops);
```

```python
# recommendation_engine.py
class VectorRecommendationEngine:
    def __init__(self, db_config: Dict):
        self.db_config = db_config
    
    def update_user_profile(self, user_id: str):
        """更新用户画像向量"""
        conn = psycopg2.connect(**self.db_config)
        
        with conn.cursor() as cur:
            # 获取用户的交互物品向量
            cur.execute("""
                SELECT 
                    iv.item_vector,
                    ui.score,
                    ui.interaction_type
                FROM user_interactions ui
                JOIN item_vectors iv ON ui.item_id = iv.item_id
                WHERE ui.user_id = %s
                ORDER BY ui.created_at DESC
                LIMIT 100
            """, (user_id,))
            
            interactions = cur.fetchall()
            
            if not interactions:
                return
            
            # 计算加权平均向量
            weighted_vectors = []
            total_weight = 0
            
            for item_vector, score, interaction_type in interactions:
                # 不同交互类型有不同的权重
                type_weights = {
                    'purchase': 3.0,
                    'like': 2.0,
                    'click': 1.0,
                    'view': 0.5
                }
                weight = score * type_weights.get(interaction_type, 1.0)
                
                weighted_vectors.append(
                    (item_vector, weight)
                )
                total_weight += weight
            
            # 计算加权平均
            profile_vector = [0.0] * 256
            for vec, weight in weighted_vectors:
                for i, v in enumerate(vec):
                    profile_vector[i] += v * weight / total_weight
            
            # 更新用户画像
            cur.execute("""
                INSERT INTO user_profiles (user_id, preference_vector, interaction_count)
                VALUES (%s, %s::vector, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    preference_vector = EXCLUDED.preference_vector,
                    interaction_count = EXCLUDED.interaction_count,
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, profile_vector, len(interactions)))
        
        conn.commit()
        conn.close()
    
    def get_recommendations(
        self,
        user_id: str,
        top_k: int = 10,
        category: Optional[str] = None
    ) -> List[Dict]:
        """获取个性化推荐"""
        conn = psycopg2.connect(**self.db_config)
        
        with conn.cursor() as cur:
            # 获取用户画像
            cur.execute("""
                SELECT preference_vector FROM user_profiles WHERE user_id = %s
            """, (user_id,))
            
            result = cur.fetchone()
            if not result:
                return self._get_popular_items(top_k, category)
            
            user_vector = result[0]
            
            # 获取用户已交互的物品
            cur.execute("""
                SELECT item_id FROM user_interactions WHERE user_id = %s
            """, (user_id,))
            
            interacted_items = {row[0] for row in cur.fetchall()}
            
            # 构建查询条件
            if category:
                cur.execute("""
                    SELECT 
                        iv.item_id,
                        iv.category,
                        iv.popularity_score,
                        1 - (iv.item_vector <=> %s::vector) AS similarity
                    FROM item_vectors iv
                    WHERE iv.category = %s
                      AND iv.item_id NOT IN (
                          SELECT item_id FROM user_interactions WHERE user_id = %s
                      )
                    ORDER BY iv.item_vector <=> %s::vector
                    LIMIT %s
                """, (user_vector, category, user_id, user_vector, top_k))
            else:
                cur.execute("""
                    SELECT 
                        iv.item_id,
                        iv.category,
                        iv.popularity_score,
                        1 - (iv.item_vector <=> %s::vector) AS similarity
                    FROM item_vectors iv
                    WHERE iv.item_id NOT IN (
                        SELECT item_id FROM user_interactions WHERE user_id = %s
                    )
                    ORDER BY iv.item_vector <=> %s::vector
                    LIMIT %s
                """, (user_vector, user_id, user_vector, top_k))
            
            results = cur.fetchall()
        
        conn.close()
        
        return [
            {
                'item_id': row[0],
                'category': row[1],
                'popularity': row[2],
                'similarity': row[3]
            }
            for row in results
        ]
    
    def get_similar_items(
        self,
        item_id: str,
        top_k: int = 10
    ) -> List[Dict]:
        """获取相似物品"""
        conn = psycopg2.connect(**self.db_config)
        
        with conn.cursor() as cur:
            # 获取物品向量
            cur.execute("""
                SELECT item_vector FROM item_vectors WHERE item_id = %s
            """, (item_id,))
            
            result = cur.fetchone()
            if not result:
                return []
            
            item_vector = result[0]
            
            # 查找相似物品
            cur.execute("""
                SELECT 
                    item_id,
                    category,
                    1 - (item_vector <=> %s::vector) AS similarity
                FROM item_vectors
                WHERE item_id != %s
                ORDER BY item_vector <=> %s::vector
                LIMIT %s
            """, (item_vector, item_id, item_vector, top_k))
            
            results = cur.fetchall()
        
        conn.close()
        
        return [
            {
                'item_id': row[0],
                'category': row[1],
                'similarity': row[2]
            }
            for row in results
        ]
```

---

## 第9章 最佳实践与性能调优

### 9.1 数据建模最佳实践

#### 9.1.1 向量表设计原则

```sql
-- 1. 使用UUID作为主键（避免顺序写入热点）
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 分离向量和元数据（减少IO）
CREATE TABLE vector_data (
    id UUID PRIMARY KEY,
    embedding vector(1536) NOT NULL
);

CREATE TABLE vector_metadata (
    id UUID PRIMARY KEY REFERENCES vector_data(id),
    title VARCHAR(500),
    content TEXT,
    category VARCHAR(100),
    tags TEXT[],
    metadata JSONB
);

-- 3. 使用分区表（大数据量）
CREATE TABLE embeddings (
    id UUID,
    embedding vector(1536),
    created_at TIMESTAMP
) PARTITION BY RANGE (created_at);
```

#### 9.1.2 索引策略

```sql
-- 1. 根据距离类型选择合适的操作符类
-- 余弦相似度（推荐用于文本）
CREATE INDEX idx_cosine ON embeddings 
USING hnsw (embedding vector_cosine_ops);

-- 欧氏距离（通用）
CREATE INDEX idx_l2 ON embeddings 
USING hnsw (embedding vector_l2_ops);

-- 内积（推荐用于推荐系统）
CREATE INDEX idx_ip ON embeddings 
USING hnsw (embedding vector_ip_ops);

-- 2. 复合索引（过滤条件+向量）
CREATE INDEX idx_category_vector ON embeddings 
USING hnsw (embedding vector_cosine_ops)
WHERE category = 'important';
```

### 9.2 查询优化

#### 9.2.1 预过滤优化

```sql
-- 差：先排序再过滤
SELECT * FROM embeddings 
ORDER BY embedding <=> query_vector 
LIMIT 10;
-- 然后再在应用层过滤

-- 好：先过滤再排序
SELECT * FROM embeddings 
WHERE category = 'tech'
ORDER BY embedding <=> query_vector 
LIMIT 10;

-- 更好：使用分区或部分索引
CREATE INDEX idx_tech_embeddings ON embeddings 
USING hnsw (embedding vector_cosine_ops)
WHERE category = 'tech';
```

#### 9.2.2 分页查询

```sql
-- 使用游标分页（推荐）
DECLARE cur CURSOR FOR
SELECT * FROM embeddings 
WHERE category = 'tech'
ORDER BY embedding <=> query_vector;

FETCH 10 FROM cur;  -- 第一页
FETCH 10 FROM cur;  -- 第二页

-- 或使用键集分页
SELECT * FROM embeddings 
WHERE category = 'tech'
  AND id > last_seen_id
ORDER BY embedding <=> query_vector
LIMIT 10;
```

### 9.3 批量操作优化

```sql
-- 批量插入（使用COPY）
COPY embeddings(content, embedding) 
FROM '/path/to/data.csv' 
WITH (FORMAT csv, HEADER true);

-- 批量更新（使用临时表）
CREATE TEMP TABLE updates (id UUID, new_embedding vector);
COPY updates FROM '/path/to/updates.csv' WITH (FORMAT csv);

UPDATE embeddings e
SET embedding = u.new_embedding
FROM updates u
WHERE e.id = u.id;

-- 批量删除
DELETE FROM embeddings
WHERE id IN (SELECT id FROM to_delete);
```

### 9.4 监控和诊断

```sql
-- 查看表大小
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size
FROM pg_tables
WHERE tablename = 'embeddings';

-- 查看索引使用情况
SELECT 
    indexrelname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- 查看慢查询
SELECT 
    query,
    calls,
    mean_exec_time,
    total_exec_time
FROM pg_stat_statements
WHERE query LIKE '%embeddings%'
ORDER BY mean_exec_time DESC
LIMIT 10;

-- 查看锁等待
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity 
    ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
WHERE NOT blocked_locks.granted;
```

### 9.5 硬件和配置建议

```
# postgresql.conf 推荐配置

# 内存配置（假设服务器有32GB内存）
shared_buffers = 8GB                    # 25% of RAM
effective_cache_size = 24GB             # 75% of RAM
work_mem = 256MB                        # 复杂查询使用
maintenance_work_mem = 2GB              # 索引构建使用

# 连接配置
max_connections = 200
shared_preload_libraries = 'pg_stat_statements'

# WAL配置
wal_buffers = 16MB
max_wal_size = 4GB
min_wal_size = 1GB

# 并行配置
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
max_parallel_maintenance_workers = 4

# pgvector特定配置
# HNSW构建时使用更多内存
SET maintenance_work_mem = '4GB';
CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops);
```

---


## 9. 生产部署

### 9.1 性能优化

**1. 数据库配置优化：**

```ini
# postgresql.conf - 生产环境推荐配置

# 连接和并发
max_connections = 200
max_parallel_workers = 16
max_parallel_workers_per_gather = 8
max_parallel_maintenance_workers = 8

# 内存配置（假设服务器64GB内存）
shared_buffers = 16GB
effective_cache_size = 48GB
work_mem = 512MB
maintenance_work_mem = 4GB

# WAL配置
wal_buffers = 64MB
max_wal_size = 8GB
min_wal_size = 2GB
checkpoint_completion_target = 0.9

# 查询规划器
random_page_cost = 1.1  # SSD存储
effective_io_concurrency = 200

# pgvector特定
shared_preload_libraries = 'pgvector'
```

**2. 连接池配置（PgBouncer）：**

```ini
# pgbouncer.ini
[databases]
vectordb = host=localhost port=5432 dbname=vectordb

[pgbouncer]
listen_port = 6432
listen_addr = 0.0.0.0
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

# 连接池配置
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 50
min_pool_size = 10
reserve_pool_size = 10
```

**3. 批量操作优化：**

```python
# 使用COPY进行大规模数据导入
import io

def bulk_import_vectors(conn, table_name, data_generator, batch_size=10000):
    """
    高效批量导入向量数据
    
    Args:
        conn: 数据库连接
        table_name: 目标表名
        data_generator: 数据生成器，yield (id, content, embedding)
        batch_size: 每批大小
    """
    cursor = conn.cursor()
    
    buffer = io.StringIO()
    count = 0
    
    for row in data_generator:
        embedding_str = '[' + ','.join(f'{x:.6f}' for x in row[2]) + ']'
        buffer.write(f"{row[0]}\t{row[1]}\t{embedding_str}\n")
        count += 1
        
        if count >= batch_size:
            buffer.seek(0)
            cursor.copy_from(
                buffer, 
                table_name, 
                columns=('id', 'content', 'embedding')
            )
            conn.commit()
            buffer = io.StringIO()
            count = 0
            print(f"已导入 {batch_size} 条记录")
    
    # 导入剩余数据
    if count > 0:
        buffer.seek(0)
        cursor.copy_from(
            buffer, 
            table_name, 
            columns=('id', 'content', 'embedding')
        )
        conn.commit()
    
    cursor.close()
```

### 9.2 监控与维护

**1. 关键监控指标：**

```sql
-- 向量表大小
SELECT 
    schemaname,
    relname,
    pg_size_pretty(pg_total_relation_size(relid)) as total_size,
    n_live_tup as live_tuples,
    n_dead_tup as dead_tuples
FROM pg_stat_user_tables
WHERE relname LIKE '%embedding%' OR relname LIKE '%vector%'
ORDER BY pg_total_relation_size(relid) DESC;

-- 索引大小和效率
SELECT 
    schemaname,
    relname as table_name,
    indexrelname as index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    idx_scan as index_scans,
    idx_tup_read as tuples_read
FROM pg_stat_user_indexes
WHERE indexrelname LIKE '%embedding%'
ORDER BY pg_relation_size(indexrelid) DESC;

-- 慢查询监控
SELECT 
    query,
    calls,
    mean_exec_time,
    total_exec_time,
    rows
FROM pg_stat_statements
WHERE query LIKE '%embedding%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**2. 定期维护任务：**

```python
import psycopg2
from datetime import datetime

class VectorDBMaintenance:
    """向量数据库维护工具"""
    
    def __init__(self, db_config):
        self.conn = psycopg2.connect(**db_config)
    
    def vacuum_analyze(self, table_name):
        """执行VACUUM和ANALYZE"""
        cursor = self.conn.cursor()
        print(f"[{datetime.now()}] 执行VACUUM ANALYZE on {table_name}")
        cursor.execute(f"VACUUM ANALYZE {table_name}")
        self.conn.commit()
        cursor.close()
    
    def reindex_if_needed(self, table_name, threshold=0.3):
        """根据膨胀率决定是否重建索引"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                indexrelname,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
                idx_scan,
                idx_tup_read
            FROM pg_stat_user_indexes
            WHERE relname = %s
        """, (table_name,))
        
        indexes = cursor.fetchall()
        
        for idx in indexes:
            index_name = idx[0]
            scans = idx[2]
            
            # 如果索引很少被使用，考虑删除
            if scans < 100:
                print(f"警告: 索引 {index_name} 使用频率低 ({scans} 次扫描)")
        
        cursor.close()
    
    def update_statistics(self, table_name):
        """更新表统计信息"""
        cursor = self.conn.cursor()
        print(f"[{datetime.now()}] 更新统计信息: {table_name}")
        cursor.execute(f"ANALYZE {table_name}")
        self.conn.commit()
        cursor.close()
    
    def run_maintenance(self, table_names):
        """运行完整维护流程"""
        for table_name in table_names:
            print(f"\n维护表: {table_name}")
            self.vacuum_analyze(table_name)
            self.reindex_if_needed(table_name)
            self.update_statistics(table_name)
    
    def close(self):
        self.conn.close()

# 定时任务脚本
if __name__ == "__main__":
    db_config = {
        "host": "localhost",
        "database": "vectordb",
        "user": "postgres",
        "password": "password"
    }
    
    maintenance = VectorDBMaintenance(db_config)
    maintenance.run_maintenance(['documents', 'products', 'images'])
    maintenance.close()
```

### 9.3 扩展性考虑

**1. 读写分离架构：**

```
                    ┌─────────────┐
                    │   应用层    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ PgBouncer│  │ PgBouncer│  │ PgBouncer│
        │ (写池)  │  │ (读池1) │  │ (读池2) │
        └────┬────┘  └────┬────┘  └────┬────┘
             │            │            │
             ▼            ▼            ▼
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ Primary │  │ Replica │  │ Replica │
        │ (写入)  │  │ (读取)  │  │ (读取)  │
        └─────────┘  └─────────┘  └─────────┘
             │            │            │
             └────────────┴────────────┘
                          │
                    ┌─────┴─────┐
                    │ 流式复制  │
                    └───────────┘
```

**2. 分区策略：**

```sql
-- 按时间分区（适合日志类数据）
CREATE TABLE document_embeddings (
    id UUID DEFAULT gen_random_uuid(),
    document_id TEXT NOT NULL,
    content TEXT,
    embedding VECTOR(1536),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 创建月度分区
CREATE TABLE document_embeddings_2024_01 
    PARTITION OF document_embeddings
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE document_embeddings_2024_02 
    PARTITION OF document_embeddings
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- 按类别分区（适合多租户场景）
CREATE TABLE tenant_embeddings (
    id SERIAL,
    tenant_id TEXT NOT NULL,
    content TEXT,
    embedding VECTOR(1536),
    PRIMARY KEY (tenant_id, id)
) PARTITION BY LIST (tenant_id);

CREATE TABLE tenant_embeddings_a 
    PARTITION OF tenant_embeddings
    FOR VALUES IN ('tenant_a');

CREATE TABLE tenant_embeddings_b 
    PARTITION OF tenant_embeddings
    FOR VALUES IN ('tenant_b');
```

**3. 水平扩展方案：**

```python
# 使用一致性哈希实现简单的分片
import hashlib

class ShardedVectorDB:
    """分片向量数据库客户端"""
    
    def __init__(self, shards):
        """
        Args:
            shards: 分片配置列表
                [{"host": "db1", "port": 5432, "database": "vectordb"}, ...]
        """
        self.shards = shards
        self.num_shards = len(shards)
    
    def _get_shard(self, key):
        """根据key获取分片"""
        hash_value = int(hashlib.md5(key.encode()).hexdigest(), 16)
        shard_index = hash_value % self.num_shards
        return self.shards[shard_index]
    
    def insert(self, key, embedding, metadata):
        """插入数据到对应分片"""
        shard = self._get_shard(key)
        # 连接到shard并插入数据
        # ...
    
    def search(self, query_embedding, top_k=10):
        """在所有分片上搜索并合并结果"""
        all_results = []
        
        for shard in self.shards:
            # 在每个分片上搜索
            # results = search_in_shard(shard, query_embedding, top_k)
            # all_results.extend(results)
            pass
        
        # 合并并排序结果
        all_results.sort(key=lambda x: x['distance'])
        return all_results[:top_k]
```

---


## 第10章 常见问题与解决方案

### 10.1 安装问题

#### Q1: 编译pgvector时出错

```bash
# 错误：make: pg_config: Command not found
# 解决：安装postgresql-server-dev包
sudo apt-get install postgresql-server-dev-16

# 错误：fatal error: postgres.h: No such file
# 解决：确保安装了开发包并设置了PG_CONFIG
export PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config
make clean && make && sudo make install
```

#### Q2: 无法创建扩展

```sql
-- 错误：ERROR: could not open extension control file
-- 解决：确认pgvector已正确安装
SHOW shared_preload_libraries;

-- 检查可用扩展
SELECT * FROM pg_available_extensions WHERE name = 'vector';

-- 如果没有，需要重新安装pgvector
```

### 10.2 性能问题

#### Q3: 查询速度慢

```sql
-- 诊断步骤

-- 1. 检查是否使用了索引
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM embeddings 
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;

-- 应该看到类似：Index Scan using idx_embeddings_hnsw

-- 2. 检查索引参数
SHOW hnsw.ef_search;  -- 默认40，可以增加到100-200

-- 3. 检查表统计信息
ANALYZE embeddings;

-- 4. 检查是否有合适的索引
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'embeddings';
```

#### Q4: 索引构建太慢

```sql
-- 解决方案

-- 1. 增加维护工作内存
SET maintenance_work_mem = '4GB';

-- 2. 使用并行构建（PostgreSQL 14+）
SET max_parallel_maintenance_workers = 4;
CREATE INDEX CONCURRENTLY ON embeddings 
USING hnsw (embedding vector_cosine_ops);

-- 3. 对于IVFFlat，减少lists数量
CREATE INDEX ON embeddings 
USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 50);  -- 而不是100
```

### 10.3 数据问题

#### Q5: 向量维度不匹配

```sql
-- 错误：ERROR: different vector dimensions

-- 检查现有数据的维度
SELECT DISTINCT vector_dims(embedding) FROM embeddings;

-- 检查表定义
\d embeddings

-- 修复：确保插入的向量维度正确
INSERT INTO embeddings (embedding) 
VALUES ('[0.1, 0.2, 0.3]'::vector(1536));  -- 明确指定维度
```

#### Q6: 相似度分数异常

```sql
-- 问题：相似度分数不在预期范围内

-- 检查向量是否已归一化
SELECT 
    vector_norm(embedding),
    embedding <=> '[0.1, 0.2, ...]'::vector AS distance
FROM embeddings
LIMIT 5;

-- 对于余弦距离，向量应该归一化
UPDATE embeddings
SET embedding = embedding / vector_norm(embedding)
WHERE id IN (...);
```

### 10.4 并发问题

#### Q7: 高并发下性能下降

```sql
-- 解决方案

-- 1. 使用连接池（PgBouncer）
-- 配置PgBouncer在事务模式下

-- 2. 分区减少锁竞争
CREATE TABLE embeddings (...) PARTITION BY HASH (id);

-- 3. 使用读写分离
-- 主库写入，从库查询

-- 4. 调整PostgreSQL锁超时
SET lock_timeout = '5s';
```

### 10.5 内存问题

#### Q8: 内存不足

```sql
-- 解决方案

-- 1. 减少shared_buffers
shared_buffers = 2GB  -- 从8GB减少

-- 2. 使用halfvec减少存储
ALTER TABLE embeddings 
ALTER COLUMN embedding TYPE halfvec(1536);

-- 3. 减少HNSW的m参数
DROP INDEX idx_embeddings_hnsw;
CREATE INDEX idx_embeddings_hnsw ON embeddings 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 8);  -- 默认16，减少到8

-- 4. 分批处理大数据集
-- 使用游标或LIMIT/OFFSET分批处理
```

### 10.6 常见问题速查表

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 扩展创建失败 | pgvector未安装 | 重新安装pgvector |
| 查询无结果 | 向量维度不匹配 | 检查并统一维度 |
| 查询速度慢 | 缺少索引 | 创建HNSW索引 |
| 召回率低 | ef_search太小 | 增加ef_search |
| 索引构建慢 | 内存不足 | 增加maintenance_work_mem |
| 写入性能差 | 索引更新开销 | 批量写入或临时禁用索引 |
| 内存占用高 | HNSW参数过大 | 减少m参数或使用IVFFlat |

---

## 附录

### A. 参考资源

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [pgvector 官方文档](https://github.com/pgvector/pgvector/blob/master/README.md)
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [Spring AI 文档](https://docs.spring.io/spring-ai/reference/)

### B. 版本兼容性

| pgvector版本 | PostgreSQL版本 | 主要特性 |
|--------------|----------------|----------|
| 0.5.x | 12-15 | HNSW索引 |
| 0.6.x | 12-16 | 并行索引构建 |
| 0.7.x | 12-16 | sparsevec类型 |
| 0.8.x | 14-17 | 性能优化 |

### C. 性能基准参考

| 数据量 | 索引类型 | 查询延迟 | 召回率 |
|--------|----------|----------|--------|
| 100K | HNSW | ~5ms | >95% |
| 1M | HNSW | ~10ms | >95% |
| 10M | HNSW | ~20ms | >90% |
| 100M | HNSW | ~50ms | >85% |

---

**文档结束**

> 本文档如有错误或遗漏，请参考官方文档。
