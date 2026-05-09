package com.nanmuli.blog.infrastructure.config.cache;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Redis缓存配置
 * 配置Spring Cache与Redis集成
 */
@Configuration
@EnableCaching
@EnableConfigurationProperties(CacheConfig.TtlProperties.class)
public class CacheConfig {

    /**
     * 缓存TTL配置属性
     * 对应 yml 中的 blog.cache.ttl.* 配置项
     */
    @Data
    @ConfigurationProperties(prefix = "blog.cache.ttl")
    public static class TtlProperties {
        /** 默认缓存过期时间 */
        private Duration defaultDuration = Duration.ofHours(1);
        /** 文章详情缓存 */
        private Duration article = Duration.ofMinutes(30);
        /** 文章列表缓存 */
        private Duration articleList = Duration.ofMinutes(10);
        /** 置顶文章缓存 */
        private Duration articleTop = Duration.ofMinutes(10);
        /** 分类缓存 */
        private Duration category = Duration.ofHours(2);
        /** 标签缓存 */
        private Duration tag = Duration.ofHours(2);
        /** 系统配置缓存 */
        private Duration config = Duration.ofDays(1);
        /** 文章归档缓存 */
        private Duration articleArchive = Duration.ofHours(1);
        /** 文章统计缓存 */
        private Duration articleStats = Duration.ofMinutes(5);
    }

    /**
     * 配置Redis缓存管理器
     */
    @Bean
    public CacheManager cacheManager(RedisConnectionFactory connectionFactory,
                                     ObjectMapper objectMapper,
                                     TtlProperties ttlProps) {

        GenericJackson2JsonRedisSerializer jsonSerializer = new GenericJackson2JsonRedisSerializer(objectMapper);

        // 默认缓存配置
        RedisCacheConfiguration defaultConfig = buildConfig(ttlProps.getDefaultDuration(), jsonSerializer);

        // 针对不同缓存名称的配置
        Map<String, RedisCacheConfiguration> cacheConfigurations = new HashMap<>();
        cacheConfigurations.put("article", buildConfig(ttlProps.getArticle(), jsonSerializer));
        cacheConfigurations.put("article:list", buildConfig(ttlProps.getArticleList(), jsonSerializer));
        cacheConfigurations.put("article:top", buildConfig(ttlProps.getArticleTop(), jsonSerializer));
        cacheConfigurations.put("category", buildConfig(ttlProps.getCategory(), jsonSerializer));
        cacheConfigurations.put("tag", buildConfig(ttlProps.getTag(), jsonSerializer));
        cacheConfigurations.put("config", buildConfig(ttlProps.getConfig(), jsonSerializer));
        cacheConfigurations.put("article:archive", buildConfig(ttlProps.getArticleArchive(), jsonSerializer));
        cacheConfigurations.put("article:stats", buildConfig(ttlProps.getArticleStats(), jsonSerializer));

        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(defaultConfig)
                .withInitialCacheConfigurations(cacheConfigurations)
                .build();
    }

    private RedisCacheConfiguration buildConfig(Duration ttl, GenericJackson2JsonRedisSerializer jsonSerializer) {
        return RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(ttl)
                .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(jsonSerializer))
                .disableCachingNullValues();
    }
}
