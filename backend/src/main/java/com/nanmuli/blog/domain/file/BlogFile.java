package com.nanmuli.blog.domain.file;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("sys_file")
public class BlogFile extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private String originalName;
    private String fileName;
    private String filePath;
    private String fileUrl;
    private String fileType;
    private Long fileSize;
    private String mimeType;
    private String md5;
    private Integer width;
    private Integer height;
    private Long userId;
    private String storageType;
    private String usageType;
    private Long refId;
}
