-- 来源可信度表：将硬编码的域名评分数据库化，支持动态管理
CREATE TABLE IF NOT EXISTS source_authority (
    id          BIGINT PRIMARY KEY,
    domain      VARCHAR(255) NOT NULL UNIQUE,
    score       INT NOT NULL DEFAULT 50,
    level       VARCHAR(20) NOT NULL DEFAULT 'medium',
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted  BOOLEAN DEFAULT FALSE
);

-- 种子数据：从 Python quality.py 硬编码列表导入
INSERT INTO source_authority (id, domain, score, level) VALUES
-- 官方/权威来源 (90-100)
(-1, 'docs.spring.io', 95, 'official'),
(-2, 'spring.io', 95, 'official'),
(-3, 'docs.python.org', 95, 'official'),
(-4, 'python.org', 95, 'official'),
(-5, 'developer.mozilla.org', 95, 'official'),
(-6, 'kubernetes.io', 95, 'official'),
(-7, 'react.dev', 95, 'official'),
(-8, 'vuejs.org', 95, 'official'),
(-9, 'docs.github.com', 95, 'official'),
(-10, 'aws.amazon.com', 95, 'official'),
(-11, 'cloud.google.com', 95, 'official'),
(-12, 'openai.com', 95, 'official'),
(-13, 'anthropic.com', 95, 'official'),
(-14, 'arxiv.org', 95, 'official'),
(-15, 'huggingface.co', 95, 'official'),
-- 高质量技术社区 (70-89)
(-100, 'medium.com', 80, 'high'),
(-101, 'dev.to', 80, 'high'),
(-102, 'stackoverflow.com', 80, 'high'),
(-103, 'infoq.com', 80, 'high'),
(-104, 'juejin.cn', 80, 'high'),
(-105, 'zhihu.com', 80, 'high'),
(-106, 'news.ycombinator.com', 80, 'high'),
(-107, 'reddit.com', 80, 'high'),
(-108, 'v2ex.com', 80, 'high'),
(-109, 'csdn.net', 80, 'high'),
(-110, 'blog.csdn.net', 80, 'high'),
(-111, 'ruanyifeng.com', 80, 'high'),
-- 技术博客 (50-69)
(-200, 'github.io', 60, 'medium'),
(-201, 'github.com', 60, 'medium'),
(-202, 'netlify.app', 60, 'medium'),
(-203, 'vercel.app', 60, 'medium')
ON CONFLICT (domain) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_source_authority_domain ON source_authority(domain) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_source_authority_level ON source_authority(level) WHERE is_deleted = FALSE;

COMMENT ON TABLE source_authority IS '来源可信度表 - 域名→评分映射，支持动态管理';
