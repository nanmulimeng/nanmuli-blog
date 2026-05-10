package com.nanmuli.blog.domain.file;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.util.Optional;

public interface FileRepository {
    BlogFile save(BlogFile file);

    Optional<BlogFile> findById(Long id);

    Optional<BlogFile> findByMd5(String md5);

    void deleteById(Long id);

    IPage<BlogFile> findPage(IPage<BlogFile> page, String keyword, String fileType);
}
