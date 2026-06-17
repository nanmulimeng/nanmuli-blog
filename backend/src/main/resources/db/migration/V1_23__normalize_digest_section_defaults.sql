-- V1.23: normalize daily digest section defaults to canonical crawler categories.
-- Keep custom admin configs intact unless they are still the old three-section seed.

UPDATE sys_config
SET default_value = '[{"name":"hot_trend","keyword":"site:github.blog GitHub Copilot coding agent developer update OR site:openai.com/blog API model release developer impact OR site:anthropic.com/news Claude API developer release OR AI security vulnerability developer impact","time_range":"week","max_items":6},{"name":"open_source","keyword":"site:github.com/trending AI developer tools OR site:github.com/trending llm agent OR site:github.com trending open source developer tool release OR site:github.com releases AI developer tool","time_range":"week","max_items":4},{"name":"dev_tool","keyword":"site:code.visualstudio.com release developer tool OR site:jetbrains.com release IDE developer tool OR site:github.blog developer workflow tool OR site:postman.com release API developer tool","time_range":"week","max_items":3},{"name":"tech_article","keyword":"site:martinfowler.com architecture AI software engineering OR site:github.blog/engineering AI developer workflow architecture OR site:cloudflare.com/blog AI agent architecture engineering OR site:netflixtechblog.com architecture reliability engineering","time_range":"week","max_items":3},{"name":"paper","keyword":"site:arxiv.org AI agent RAG LLM systems paper OR site:openreview.net language model agent paper OR site:paperswithcode.com LLM agent benchmark","time_range":"week","max_items":3}]'
WHERE config_key = 'crawler.digest.sections'
  AND is_deleted = FALSE;

UPDATE sys_config
SET config_value = default_value
WHERE config_key = 'crawler.digest.sections'
  AND is_deleted = FALSE
  AND config_value LIKE '%"name":"news"%'
  AND config_value LIKE '%"name":"articles"%'
  AND config_value LIKE '%"name":"opensource"%';
