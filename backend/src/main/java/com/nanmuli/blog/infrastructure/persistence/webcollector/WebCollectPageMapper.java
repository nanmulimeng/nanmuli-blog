package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.webcollector.WebCollectPage;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Select;

import java.util.List;

/**
 * 爬取页面 Mapper
 */
@Mapper
public interface WebCollectPageMapper extends BaseMapper<WebCollectPage> {

    String WEB_COLLECT_PAGE_COLUMNS = """
            id,
            task_id,
            url,
            page_title,
            raw_markdown,
            page_metadata,
            crawl_status,
            error_message,
            crawl_duration,
            word_count,
            url_hash,
            content_hash,
            sort_order,
            depth,
            published_at,
            created_at,
            updated_at,
            is_deleted
            """;

    @Select("SELECT " + WEB_COLLECT_PAGE_COLUMNS + " FROM web_collect_page WHERE task_id = #{taskId} ORDER BY sort_order")
    List<WebCollectPage> selectByTaskIdOrderBySortOrder(@Param("taskId") Long taskId);

    @Select("SELECT " + WEB_COLLECT_PAGE_COLUMNS + " FROM web_collect_page WHERE task_id = #{taskId}")
    List<WebCollectPage> selectByTaskId(@Param("taskId") Long taskId);

    @Select("SELECT " + WEB_COLLECT_PAGE_COLUMNS + " FROM web_collect_page WHERE url_hash = #{urlHash} AND created_at > NOW() - INTERVAL '30 days' LIMIT 1")
    WebCollectPage selectByUrlHash(@Param("urlHash") String urlHash);

    @Select("SELECT COUNT(*) FROM web_collect_page WHERE url_hash = #{urlHash} AND created_at > NOW() - INTERVAL '30 days'")
    long countByUrlHash(@Param("urlHash") String urlHash);

    @Select("SELECT COUNT(*) FROM web_collect_page WHERE task_id = #{taskId}")
    long countByTaskId(@Param("taskId") Long taskId);

    @Select("SELECT COUNT(*) FROM web_collect_page WHERE task_id = #{taskId} AND crawl_status = #{crawlStatus}")
    long countByTaskIdAndCrawlStatus(@Param("taskId") Long taskId, @Param("crawlStatus") Integer crawlStatus);

    @Delete("DELETE FROM web_collect_page WHERE task_id = #{taskId}")
    void deleteByTaskId(@Param("taskId") Long taskId);
}
