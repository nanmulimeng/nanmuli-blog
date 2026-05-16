-- ============================================
-- V1.14: 日报板块配置扩展为 3 板块
-- 修复 Python/Java 默认值不一致问题
-- ============================================

UPDATE sys_config
SET config_value = '[{"name":"news","keyword":"tech news 最新技术动态","time_range":"day","max_items":5},{"name":"articles","keyword":"技术文章 教程 tutorial","time_range":"week","max_items":5},{"name":"opensource","keyword":"open source 开源项目 GitHub","time_range":"week","max_items":5}]',
    default_value = '[{"name":"news","keyword":"tech news 最新技术动态","time_range":"day","max_items":5},{"name":"articles","keyword":"技术文章 教程 tutorial","time_range":"week","max_items":5},{"name":"opensource","keyword":"open source 开源项目 GitHub","time_range":"week","max_items":5}]'
WHERE config_key = 'crawler.digest.sections' AND is_deleted = false;
