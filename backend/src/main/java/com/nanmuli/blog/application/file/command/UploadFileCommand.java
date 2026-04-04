package com.nanmuli.blog.application.file.command;

import lombok.Data;

@Data
public class UploadFileCommand {
    private String originalName;
    private String contentType;
    private Long fileSize;
    private byte[] content;
}
