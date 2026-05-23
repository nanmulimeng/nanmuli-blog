-- 初始化管理员用户
-- 用户名: admin, 密码: admin123
-- BCrypt 加密后的密码: $2a$10$L6YrzL7XRPy7S0FL3zUdNuer8d2WGZ5VICnomMZpz71LI0DsRf.xq

INSERT INTO sys_user (id, username, password, nickname, avatar, email, role, status, created_at, updated_at, is_deleted)
SELECT 1, 'admin', '$2a$10$L6YrzL7XRPy7S0FL3zUdNuer8d2WGZ5VICnomMZpz71LI0DsRf.xq', '管理员', '', 'admin@nanmuli.com', 'admin', 1, NOW(), NOW(), false
WHERE NOT EXISTS (SELECT 1 FROM sys_user WHERE username = 'admin');

-- 幂等迁移：V1_16 信息源源效能追踪字段
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS fail_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS avg_quality_score DOUBLE PRECISION DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS last_result_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS last_error TEXT;

-- 幂等迁移：V1_19 乐观锁字段
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 0;

-- 幂等迁移：V1_20 订阅源名称唯一约束（仅未删除记录）
CREATE UNIQUE INDEX IF NOT EXISTS uk_source_name_active ON web_collect_source (name) WHERE is_deleted = false;
