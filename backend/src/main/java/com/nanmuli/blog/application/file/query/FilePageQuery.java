package com.nanmuli.blog.application.file.query;

import com.nanmuli.blog.shared.query.BasePageQuery;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = false)
public class FilePageQuery extends BasePageQuery {

    private String keyword;

    private String fileType;  // 'image' | 'document' | 'other'
}
