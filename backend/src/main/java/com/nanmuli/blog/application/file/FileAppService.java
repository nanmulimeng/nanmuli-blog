package com.nanmuli.blog.application.file;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.springframework.util.DigestUtils;
import com.nanmuli.blog.application.file.command.UploadFileCommand;
import com.nanmuli.blog.application.file.dto.FileDTO;
import com.nanmuli.blog.application.file.query.FilePageQuery;
import com.nanmuli.blog.domain.file.BlogFile;
import com.nanmuli.blog.domain.file.FileRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import com.nanmuli.blog.shared.result.PageResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class FileAppService {

    private static final Map<String, String> EXTENSION_TO_MIME = Map.ofEntries(
            Map.entry("jpg", "image/jpeg"), Map.entry("jpeg", "image/jpeg"),
            Map.entry("png", "image/png"), Map.entry("gif", "image/gif"),
            Map.entry("webp", "image/webp"), Map.entry("svg", "image/svg+xml"),
            Map.entry("txt", "text/plain"), Map.entry("md", "text/markdown"),
            Map.entry("pdf", "application/pdf"),
            Map.entry("zip", "application/zip"), Map.entry("rar", "application/x-rar-compressed"),
            Map.entry("7z", "application/x-7z-compressed")
    );

    private final FileRepository fileRepository;
    private final ImageThumbnailService imageThumbnailService;

    @Value("${blog.file.upload-path:./uploads}")
    private String uploadPath;

    @Value("${blog.file.access-url:/uploads/}")
    private String accessUrl;

    @Value("${blog.file.max-size:10485760}")
    private long maxFileSize;

    @Value("${blog.file.allowed-extensions:jpg,jpeg,png,gif,webp,svg,txt,md,pdf,zip,rar,7z}")
    private String allowedExtensionsConfig;

    @Value("${blog.file.storage-type:local}")
    private String storageType;

    // 常见文件类型的Magic Number
    private static final Map<String, byte[]> MAGIC_NUMBERS = Map.of(
            "jpg", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF},
            "jpeg", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF},
            "png", new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47},
            "gif", new byte[]{0x47, 0x49, 0x46, 0x38},
            "pdf", new byte[]{0x25, 0x50, 0x44, 0x46},
            "webp", new byte[]{0x52, 0x49, 0x46, 0x46}
    );

    /**
     * 解析配置的允许扩展名为 Set
     */
    private Set<String> getAllowedExtensions() {
        return Set.of(allowedExtensionsConfig.split(","));
    }

    @Transactional
    public FileDTO upload(UploadFileCommand command) {
        String originalName = command.getOriginalName();
        if (!StringUtils.hasText(originalName)) {
            throw new BusinessException("文件名不能为空");
        }

        String extension = getExtension(originalName).toLowerCase(Locale.ROOT);
        Set<String> allowedExtensions = getAllowedExtensions();
        if (!allowedExtensions.contains(extension)) {
            throw new BusinessException("不支持的文件类型");
        }

        // 文件大小限制检查
        if (command.getFileSize() > maxFileSize) {
            throw new BusinessException("文件大小超过限制");
        }

        // Magic Number校验：验证文件实际类型与扩展名是否一致
        if (!isValidFileType(command.getContent(), extension)) {
            throw new BusinessException("文件类型与扩展名不符，可能存在安全风险");
        }

        String contentType = command.getContentType();
        if (contentType != null) {
            String expectedMime = EXTENSION_TO_MIME.get(extension);
            if (expectedMime != null && !expectedMime.equalsIgnoreCase(contentType)) {
                // 扩展名与 Content-Type 不匹配时检查是否在已知 MIME 映射中
                if (!EXTENSION_TO_MIME.containsValue(contentType.toLowerCase(Locale.ROOT))) {
                    throw new BusinessException("不支持的文件格式");
                }
            }
        }

        String md5 = DigestUtils.md5DigestAsHex(command.getContent());

        Optional<BlogFile> existing = fileRepository.findByMd5(md5);
        if (existing.isPresent()) {
            return convertToDTO(existing.get());
        }

        String fileName = UUID.randomUUID().toString().replace("-", "") + "." + extension;
        Path targetDir = Paths.get(uploadPath);
        Path targetPath = targetDir.resolve(fileName);

        try {
            if (!Files.exists(targetDir)) {
                Files.createDirectories(targetDir);
            }
            Files.write(targetPath, command.getContent());
        } catch (Exception e) {
            log.error("文件写入磁盘失败, path={}", targetPath, e);
            throw new BusinessException("文件保存失败");
        }

        // 生成缩略图（仅图片类型）
        ImageThumbnailService.ThumbnailResult thumbResult =
                imageThumbnailService.generate(command.getContent(), contentType, fileName, targetDir, accessUrl);

        BlogFile blogFile = new BlogFile();
        blogFile.setOriginalName(originalName);
        blogFile.setFileName(fileName);
        blogFile.setFilePath(targetPath.toString());
        blogFile.setFileUrl(accessUrl + fileName);
        blogFile.setFileSize(command.getFileSize());
        blogFile.setMimeType(contentType);
        blogFile.setFileType(contentType);
        blogFile.setMd5(md5);
        blogFile.setStorageType(storageType);
        if (thumbResult != null) {
            blogFile.setWidth(thumbResult.width());
            blogFile.setHeight(thumbResult.height());
            blogFile.setThumbnailUrl(thumbResult.thumbnailUrl());
        }
        fileRepository.save(blogFile);

        log.info("文件上传成功, fileName={}, md5={}, size={}", fileName, md5, command.getFileSize());
        return convertToDTO(blogFile);
    }

    /**
     * 校验文件Magic Number，验证文件实际类型与扩展名是否一致
     */
    private boolean isValidFileType(byte[] fileData, String extension) {
        if (fileData == null || fileData.length < 4) {
            return false;
        }

        byte[] expected = MAGIC_NUMBERS.get(extension.toLowerCase(Locale.ROOT));
        if (expected == null) {
            // 未知类型不做Magic Number校验（如txt、md、zip等）
            return true;
        }

        // 特殊处理webp：需要检查文件偏移8处的WEBP标识
        if ("webp".equals(extension.toLowerCase(Locale.ROOT))) {
            return fileData.length >= 12 &&
                   fileData[0] == 0x52 && fileData[1] == 0x49 && fileData[2] == 0x46 && fileData[3] == 0x46 &&
                   fileData[8] == 0x57 && fileData[9] == 0x45 && fileData[10] == 0x42 && fileData[11] == 0x50;
        }

        for (int i = 0; i < expected.length; i++) {
            if (fileData[i] != expected[i]) {
                return false;
            }
        }
        return true;
    }

    @Transactional(readOnly = true)
    public FileDTO getById(Long id) {
        return fileRepository.findById(id)
                .map(this::convertToDTO)
                .orElseThrow(() -> new BusinessException("文件不存在"));
    }

    @Transactional(readOnly = true)
    public PageResult<FileDTO> list(FilePageQuery query) {
        IPage<BlogFile> page = new Page<>(query.getCurrent(), query.getSize());
        IPage<BlogFile> result = fileRepository.findPage(page, query.getKeyword(), query.getFileType());
        List<FileDTO> records = result.getRecords().stream().map(this::convertToDTO).toList();
        return new PageResult<>(result.getTotal(), result.getCurrent(), result.getSize(), records);
    }

    /**
     * 为已有文件重新生成缩略图（用于后补历史数据）
     */
    @Transactional
    public int regenerateMissingThumbnails() {
        List<BlogFile> allFiles = fileRepository.findAll();
        int count = 0;
        for (BlogFile file : allFiles) {
            String mimeType = file.getMimeType();
            if (mimeType == null || !mimeType.startsWith("image/")) continue;
            if (file.getThumbnailUrl() != null && file.getWidth() != null) continue;

            Path filePath = Paths.get(file.getFilePath());
            if (!Files.exists(filePath)) {
                log.warn("文件不存在, 跳过缩略图生成: {}", file.getFilePath());
                continue;
            }
            try {
                byte[] fileData = Files.readAllBytes(filePath);
                String baseFileName = file.getFileName();
                ImageThumbnailService.ThumbnailResult result =
                        imageThumbnailService.generate(fileData, mimeType, baseFileName, Paths.get(uploadPath), accessUrl);
                if (result != null) {
                    file.setWidth(result.width());
                    file.setHeight(result.height());
                    file.setThumbnailUrl(result.thumbnailUrl());
                    fileRepository.save(file);
                    count++;
                }
            } catch (Exception e) {
                log.error("缩略图重新生成失败, fileId={}", file.getId(), e);
            }
        }
        log.info("缩略图后补完成, 共处理 {} 个文件", count);
        return count;
    }

    @Transactional
    public void delete(Long id) {
        BlogFile file = fileRepository.findById(id)
                .orElseThrow(() -> new BusinessException("文件不存在"));
        fileRepository.deleteById(id);
        // 逻辑删除不删物理文件，保留数据安全性
    }

    private FileDTO convertToDTO(BlogFile blogFile) {
        FileDTO dto = new FileDTO();
        dto.setId(blogFile.getId());
        dto.setOriginalName(blogFile.getOriginalName());
        dto.setFileUrl(blogFile.getFileUrl());
        dto.setThumbnailUrl(blogFile.getThumbnailUrl());
        dto.setWidth(blogFile.getWidth());
        dto.setHeight(blogFile.getHeight());
        dto.setFileSize(blogFile.getFileSize());
        dto.setMimeType(blogFile.getMimeType());
        dto.setStorageType(blogFile.getStorageType());
        dto.setCreateTime(blogFile.getCreatedAt());
        return dto;
    }

    private String getExtension(String filename) {
        int dotIndex = filename.lastIndexOf('.');
        return dotIndex == -1 || dotIndex == filename.length() - 1 ? "" : filename.substring(dotIndex + 1);
    }
}
