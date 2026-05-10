package com.nanmuli.blog.infrastructure.persistence.file;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.file.BlogFile;
import com.nanmuli.blog.domain.file.FileRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;
import org.springframework.util.StringUtils;

import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class FileRepositoryImpl implements FileRepository {

    private final BlogFileMapper blogFileMapper;

    @Override
    public BlogFile save(BlogFile file) {
        if (file.isNew()) {
            blogFileMapper.insert(file);
        } else {
            blogFileMapper.updateById(file);
        }
        return file;
    }

    @Override
    public Optional<BlogFile> findById(Long id) {
        return Optional.ofNullable(blogFileMapper.selectById(id));
    }

    @Override
    public Optional<BlogFile> findByMd5(String md5) {
        LambdaQueryWrapper<BlogFile> wrapper = Wrappers.lambdaQuery();
        wrapper.eq(BlogFile::getMd5, md5);
        return Optional.ofNullable(blogFileMapper.selectOne(wrapper));
    }

    @Override
    public void deleteById(Long id) {
        blogFileMapper.deleteById(id);
    }

    @Override
    public IPage<BlogFile> findPage(IPage<BlogFile> page, String keyword, String fileType) {
        LambdaQueryWrapper<BlogFile> wrapper = Wrappers.lambdaQuery();
        if (StringUtils.hasText(keyword)) {
            wrapper.like(BlogFile::getOriginalName, keyword);
        }
        if ("image".equals(fileType)) {
            wrapper.likeRight(BlogFile::getMimeType, "image/");
        } else if ("document".equals(fileType)) {
            wrapper.and(w -> w
                .likeRight(BlogFile::getMimeType, "application/")
                .or()
                .likeRight(BlogFile::getMimeType, "text/"));
        }
        wrapper.orderByDesc(BlogFile::getCreatedAt);
        wrapper.select(BlogFile::getId, BlogFile::getOriginalName, BlogFile::getFileUrl,
                BlogFile::getThumbnailUrl, BlogFile::getWidth, BlogFile::getHeight,
                BlogFile::getFileSize, BlogFile::getMimeType, BlogFile::getStorageType,
                BlogFile::getCreatedAt);
        return blogFileMapper.selectPage(page, wrapper);
    }
}
