package com.nanmuli.blog.infrastructure.config.web;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

/**
 * Web 配置
 */
@Configuration
public class WebConfig {

    @Value("${http.client.connect-timeout:5000}")
    private int connectTimeout;

    @Value("${http.client.read-timeout:120000}")
    private int readTimeout;

    /**
     * RestTemplate Bean
     * 用于调用外部 HTTP 服务（如 Python 爬虫服务）
     */
    @Bean
    public RestTemplate restTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connectTimeout);
        factory.setReadTimeout(readTimeout);
        return new RestTemplate(factory);
    }
}
