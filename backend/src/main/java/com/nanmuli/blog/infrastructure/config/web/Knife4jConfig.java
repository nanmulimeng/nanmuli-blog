package com.nanmuli.blog.infrastructure.config.web;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import org.springdoc.core.models.GroupedOpenApi;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class Knife4jConfig {

    @Bean
    public OpenAPI openAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("Nanmuli Blog API")
                        .description("个人技术博客系统后端 API 文档")
                        .version("v1.0.0")
                        .contact(new Contact().name("nanmuli")));
    }

    @Bean
    public GroupedOpenApi blogApi() {
        return GroupedOpenApi.builder()
                .group("blog")
                .pathsToMatch("/api/**")
                .build();
    }
}
