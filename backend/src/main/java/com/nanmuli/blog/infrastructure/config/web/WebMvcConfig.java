package com.nanmuli.blog.infrastructure.config.web;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.List;

@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    @Value("${cors.allowed-origins:}")
    private String allowedOrigins;

    @Value("${cors.max-age:3600}")
    private long corsMaxAge;

    @Value("${cors.allowed-methods:GET,POST,PUT,DELETE,OPTIONS}")
    private String allowedMethods;

    @Value("${blog.file.access-url:/uploads/}")
    private String accessUrl;

    @Value("${blog.file.upload-path:./uploads}")
    private String uploadPath;

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOriginPatterns(resolveOriginPatterns())
                .allowedMethods(allowedMethods.split(","))
                .allowedHeaders("*")
                .maxAge(corsMaxAge);
    }

    private String[] resolveOriginPatterns() {
        if (allowedOrigins == null || allowedOrigins.isBlank()) {
            return new String[]{"*"};
        }
        List<String> origins = List.of(allowedOrigins.split(","));
        return origins.stream()
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toArray(String[]::new);
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        registry.addResourceHandler(accessUrl + "**")
                .addResourceLocations("file:" + uploadPath + "/");
    }
}
