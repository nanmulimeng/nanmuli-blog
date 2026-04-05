-- 初始化管理员用户
-- 用户名: admin, 密码: admin123
-- BCrypt 加密后的密码: $2a$10$L6YrzL7XRPy7S0FL3zUdNuer8d2WGZ5VICnomMZpz71LI0DsRf.xq

INSERT INTO sys_user (id, username, password, nickname, avatar, email, role, status, created_at, updated_at, is_deleted)
SELECT 1, 'admin', '$2a$10$L6YrzL7XRPy7S0FL3zUdNuer8d2WGZ5VICnomMZpz71LI0DsRf.xq', '管理员', '', 'admin@nanmuli.com', 'admin', 1, NOW(), NOW(), false
WHERE NOT EXISTS (SELECT 1 FROM sys_user WHERE username = 'admin');
