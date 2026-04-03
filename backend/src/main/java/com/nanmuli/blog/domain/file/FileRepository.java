package com.nanmuli.blog.domain.file;

import java.util.Optional;

public interface FileRepository {
    BlogFile save(BlogFile file);

    Optional<BlogFile> findById(Long id);

    Optional<BlogFile> findByMd5(String md5);

    void deleteById(Long id);
}
