package com.nanmuli.blog.application.file;

import com.nanmuli.blog.domain.file.BlogFile;
import com.nanmuli.blog.domain.file.FileRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

@Service
@RequiredArgsConstructor
public class FileAppService {

    private final FileRepository fileRepository;

    @Transactional
    public BlogFile upload(MultipartFile file) {
        try {
            BlogFile blogFile = new BlogFile();
            blogFile.setOriginalName(file.getOriginalFilename());
            blogFile.setFileName(System.currentTimeMillis() + "_" + file.getOriginalFilename());
            blogFile.setFileSize(file.getSize());
            blogFile.setMimeType(file.getContentType());
            blogFile.setFileType(file.getContentType());
            blogFile.setFileUrl("/uploads/" + blogFile.getFileName());
            blogFile.setStorageType("local");
            fileRepository.save(blogFile);
            return blogFile;
        } catch (Exception e) {
            throw new BusinessException("文件上传失败");
        }
    }

    @Transactional(readOnly = true)
    public BlogFile getById(Long id) {
        return fileRepository.findById(id)
                .orElseThrow(() -> new BusinessException("文件不存在"));
    }
}
