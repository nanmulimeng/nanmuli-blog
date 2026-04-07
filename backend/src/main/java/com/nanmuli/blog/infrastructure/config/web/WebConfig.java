package com.nanmuli.blog.infrastructure.config.web;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

/**
 * Web 配置
 */
@Configuration
public class WebConfig {

    /**
     * RestTemplate Bean
     * 用于调用外部 HTTP 服务（如 Python 爬虫服务）
     */
    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
