package com.nanmuli.blog.application.file;

import org.springframework.util.DigestUtils;
import com.nanmuli.blog.application.file.command.UploadFileCommand;
import com.nanmuli.blog.application.file.dto.FileDTO;
import com.nanmuli.blog.domain.file.BlogFile;
import com.nanmuli.blog.domain.file.FileRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class FileAppService {

    // 最大文件大小：10MB
    private static final long MAX_FILE_SIZE = 10 * 1024 * 1024;

    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(
            "jpg", "jpeg", "png", "gif", "webp", "svg",
            "txt", "md", "pdf",
            "zip", "rar", "7z"
    );

    private static final Set<String> ALLOWED_MIME_TYPES = Set.of(
            "image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml",
            "text/plain", "text/markdown", "application/pdf",
            "application/zip", "application/x-rar-compressed", "application/x-7z-compressed"
    );

    private final FileRepository fileRepository;

    @Value("${blog.file.upload-path:./uploads}")
    private String uploadPath;

    // 常见文件类型的Magic Number
    private static final Map<String, byte[]> MAGIC_NUMBERS = Map.of(
            "jpg", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF},
            "jpeg", new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF},
            "png", new byte[]{(byte) 0x89, 0x50, 0x4E, 0x47},
            "gif", new byte[]{0x47, 0x49, 0x46, 0x38},
            "pdf", new byte[]{0x25, 0x50, 0x44, 0x46},
            "webp", new byte[]{0x52, 0x49, 0x46, 0x46}
    );

    @Transactional
    public FileDTO upload(UploadFileCommand command) {
        String originalName = command.getOriginalName();
        if (!StringUtils.hasText(originalName)) {
            throw new BusinessException("文件名不能为空");
        }

        String extension = getExtension(originalName).toLowerCase(Locale.ROOT);
        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            throw new BusinessException("不支持的文件类型");
        }

        // 文件大小限制检查
        if (command.getFileSize() > MAX_FILE_SIZE) {
            throw new BusinessException("文件大小超过限制（最大10MB）");
        }

        // Magic Number校验：验证文件实际类型与扩展名是否一致
        if (!isValidFileType(command.getContent(), extension)) {
            throw new BusinessException("文件类型与扩展名不符，可能存在安全风险");
        }

        String contentType = command.getContentType();
        if (contentType != null && !ALLOWED_MIME_TYPES.contains(contentType.toLowerCase(Locale.ROOT))) {
            throw new BusinessException("不支持的文件格式");
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

        BlogFile blogFile = new BlogFile();
        blogFile.setOriginalName(originalName);
        blogFile.setFileName(fileName);
        blogFile.setFilePath(targetPath.toString());
        blogFile.setFileUrl("/uploads/" + fileName);
        blogFile.setFileSize(command.getFileSize());
        blogFile.setMimeType(contentType);
        blogFile.setFileType(contentType);
        blogFile.setMd5(md5);
        blogFile.setStorageType("local");
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

    private FileDTO convertToDTO(BlogFile blogFile) {
        FileDTO dto = new FileDTO();
        dto.setId(blogFile.getId());
        dto.setOriginalName(blogFile.getOriginalName());
        dto.setFileUrl(blogFile.getFileUrl());
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
