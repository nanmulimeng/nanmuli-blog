package com.nanmuli.blog.infrastructure.config;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.embedding.EmbeddingClient;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * AI配置类
 * 配置Spring AI相关组件
 */
@Configuration
public class AiConfig {

    /**
     * 配置ChatClient
     * 使用DashScope默认模型
     */
    @Bean
    public ChatClient chatClient(ChatClient.Builder builder) {
        return builder.build();
    }
}
