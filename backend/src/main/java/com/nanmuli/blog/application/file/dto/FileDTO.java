package com.nanmuli.blog.application.file.dto;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * 文件DTO
 * 用于文件信息的传输，避免直接暴露领域实体
 */
@Data
public class FileDTO {

    private Long id;

    /**
     * 原始文件名
     */
    private String originalName;

    /**
     * 访问URL
     */
    private String fileUrl;

    /**
     * 文件大小（字节）
     */
    private Long fileSize;

    /**
     * MIME类型
     */
    private String mimeType;

    /**
     * 存储类型
     */
    private String storageType;

    /**
     * 创建时间
     */
    private LocalDateTime createdAt;
}
