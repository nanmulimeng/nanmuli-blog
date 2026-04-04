package com.nanmuli.blog.domain.ai;

import java.util.List;
import java.util.concurrent.CompletableFuture;

/**
 * AI服务接口 - 领域层防腐层
 * 定义AI能力，与具体AI提供商解耦
 */
public interface AiService {

    /**
     * 生成文章标签
     *
     * @param content 文章内容
     * @return 标签列表
     */
    CompletableFuture<List<String>> generateTags(String content);

    /**
     * 生成文章摘要
     *
     * @param content 文章内容
     * @param maxLength 最大长度
     * @return 摘要内容
     */
    CompletableFuture<String> generateSummary(String content, int maxLength);

    /**
     * 生成文章向量嵌入
     *
     * @param content 文章内容
     * @return 向量数组
     */
    CompletableFuture<float[]> generateEmbedding(String content);

    /**
     * 优化文章标题
     *
     * @param title 原标题
     * @param content 文章内容
     * @return 优化后的标题
     */
    CompletableFuture<String> optimizeTitle(String title, String content);
}
