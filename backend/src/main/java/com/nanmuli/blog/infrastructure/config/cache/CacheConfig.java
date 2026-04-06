package com.nanmuli.blog.infrastructure.config.cache;

import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
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

/**
 * Redis缓存配置
 * 配置Spring Cache与Redis集成
 */
@Configuration
@EnableCaching
public class CacheConfig {

    /**
     * 配置Redis缓存管理器
     */
    @Bean
    public CacheManager cacheManager(RedisConnectionFactory connectionFactory) {
        // 配置ObjectMapper以支持Java 8日期时间类型
        ObjectMapper objectMapper = new ObjectMapper();
        objectMapper.registerModule(new JavaTimeModule());
        objectMapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        objectMapper.activateDefaultTyping(
                objectMapper.getPolymorphicTypeValidator(),
                ObjectMapper.DefaultTyping.NON_FINAL,
                JsonTypeInfo.As.PROPERTY
        );

        GenericJackson2JsonRedisSerializer jsonSerializer = new GenericJackson2JsonRedisSerializer(objectMapper);

        // 默认缓存配置（1小时过期）
        RedisCacheConfiguration defaultConfig = RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofHours(1))
                .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(jsonSerializer))
                .disableCachingNullValues();

        // 针对不同缓存名称的配置
        return RedisCacheManager.builder(connectionFactory)
                .cacheDefaults(defaultConfig)
                .withCacheConfiguration("article", RedisCacheConfiguration.defaultCacheConfig()
                        .entryTtl(Duration.ofMinutes(30))) // 文章缓存30分钟
                .withCacheConfiguration("article:list", RedisCacheConfiguration.defaultCacheConfig()
                        .entryTtl(Duration.ofMinutes(10))) // 文章列表缓存10分钟
                .withCacheConfiguration("category", RedisCacheConfiguration.defaultCacheConfig()
                        .entryTtl(Duration.ofHours(2))) // 分类缓存2小时
                .withCacheConfiguration("tag", RedisCacheConfiguration.defaultCacheConfig()
                        .entryTtl(Duration.ofHours(2))) // 标签缓存2小时
                .withCacheConfiguration("config", RedisCacheConfiguration.defaultCacheConfig()
                        .entryTtl(Duration.ofDays(1))) // 系统配置缓存1天
                .withCacheConfiguration("article:archive", RedisCacheConfiguration.defaultCacheConfig()
                        .entryTtl(Duration.ofHours(1))) // 文章归档缓存1小时
                .withCacheConfiguration("article:stats", RedisCacheConfiguration.defaultCacheConfig()
                        .entryTtl(Duration.ofMinutes(5))) // 文章统计缓存5分钟
                .build();
    }
}
