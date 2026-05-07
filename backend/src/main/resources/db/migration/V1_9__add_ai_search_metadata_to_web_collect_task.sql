ALTER TABLE web_collect_task
    ADD COLUMN IF NOT EXISTS ai_search_metadata TEXT;

COMMENT ON COLUMN web_collect_task.ai_search_metadata IS '关键词 AI 中间产物 JSON（原词/优化词/搜索变体）';
