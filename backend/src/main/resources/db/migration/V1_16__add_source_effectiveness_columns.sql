-- V1.16: 信息源源效能追踪字段
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS fail_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS avg_quality_score DOUBLE PRECISION DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS last_result_count INTEGER DEFAULT 0;
ALTER TABLE web_collect_source ADD COLUMN IF NOT EXISTS last_error TEXT;

COMMENT ON COLUMN web_collect_source.success_count IS '成功执行次数';
COMMENT ON COLUMN web_collect_source.fail_count IS '失败执行次数';
COMMENT ON COLUMN web_collect_source.avg_quality_score IS '质量分指数移动平均(0-100)';
COMMENT ON COLUMN web_collect_source.last_result_count IS '最近一次成功运行产出的有效页面数';
COMMENT ON COLUMN web_collect_source.last_error IS '最近一次失败错误信息';
