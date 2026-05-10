package com.nanmuli.blog.infrastructure.config.cache;

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
import org.springframework.data.redis.serializer.JdkSerializationRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Redis缓存配置
 * 使用 JDK 序列化替代 JSON 序列化，确保 List 等集合类型可正确缓存
 */
@Configuration
@EnableCaching
@EnableConfigurationProperties(CacheConfig.TtlProperties.class)
public class CacheConfig {

    @Data
    @ConfigurationProperties(prefix = "blog.cache.ttl")
    public static class TtlProperties {
        private Duration defaultDuration = Duration.ofHours(1);
        private Duration article = Duration.ofMinutes(30);
        private Duration articleList = Duration.ofMinutes(10);
        private Duration articleTop = Duration.ofMinutes(10);
        private Duration category = Duration.ofHours(2);
        private Duration tag = Duration.ofHours(2);
        private Duration config = Duration.ofDays(1);
        private Duration articleArchive = Duration.ofHours(1);
        private Duration articleStats = Duration.ofMinutes(5);
    }

    @Bean
    public CacheManager cacheManager(RedisConnectionFactory connectionFactory, TtlProperties ttlProps) {
        JdkSerializationRedisSerializer jdkSerializer = new JdkSerializationRedisSerializer();

        RedisCacheConfiguration defaultConfig = buildConfig(ttlProps.getDefaultDuration(), jdkSerializer);

        Map<String, RedisCacheConfiguration> cacheConfigurations = new HashMap<>();
        cacheConfigurations.put("article", buildConfig(ttlProps.getArticle(), jdkSerializer));
        cacheConfigurations.put("article:list", buildConfig(ttlProps.getArticleList(), jdkSerializer));
        cacheConfigurations.put("article:top", buildConfig(ttlProps.getArticleTop(), jdkSerializer));
        cacheConfigurations.put("category", buildConfig(ttlProps.getCategory(), jdkSerializer));
        cacheConfigurations.put("tag", buildConfig(ttlProps.getTag(), jdkSerializer));
        cacheConfigurations.put("config", buildConfig(ttlProps.getConfig(), jdkSerializer));
        cacheConfigurations.put("article:archive", buildConfig(ttlProps.getArticleArchive(), jdkSerializer));
        cacheConfigurations.put("article:stats", buildConfig(ttlProps.getArticleStats(), jdkSerializer));

        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(defaultConfig)
                .withInitialCacheConfigurations(cacheConfigurations)
                .build();
    }

    private RedisCacheConfiguration buildConfig(Duration ttl, JdkSerializationRedisSerializer jdkSerializer) {
        return RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(ttl)
                .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(jdkSerializer))
                .disableCachingNullValues();
    }
}
