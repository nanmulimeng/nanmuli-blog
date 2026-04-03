package com.nanmuli.blog.infrastructure.persistence.file;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import com.nanmuli.blog.domain.file.BlogFile;
import com.nanmuli.blog.domain.file.FileRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

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
}
