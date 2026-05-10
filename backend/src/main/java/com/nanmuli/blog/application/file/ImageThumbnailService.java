package com.nanmuli.blog.application.file;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import javax.imageio.ImageIO;
import java.awt.*;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Set;

/**
 * 图片缩略图生成器，上传时同步生成 400px 宽 JPEG 缩略图
 */
@Slf4j
@Component
public class ImageThumbnailService {

    private static final int THUMB_WIDTH = 400;
    private static final Set<String> SUPPORTED_TYPES = Set.of(
            "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"
    );

    public record ThumbnailResult(int width, int height, String thumbnailUrl) {}

    /**
     * 如果文件是支持的图片格式，生成缩略图并返回尺寸与缩略图URL
     */
    public ThumbnailResult generate(byte[] fileData, String mimeType,
                                     String baseFileName, Path uploadDir,
                                     String accessUrl) {
        if (mimeType == null || !SUPPORTED_TYPES.contains(mimeType.toLowerCase())) {
            log.debug("跳过缩略图生成, mimeType={}", mimeType);
            return null;
        }

        try {
            BufferedImage original = ImageIO.read(new ByteArrayInputStream(fileData));
            if (original == null) {
                log.warn("无法解码图片, 跳过缩略图生成");
                return null;
            }

            int origW = original.getWidth();
            int origH = original.getHeight();

            int thumbH = (int) Math.round((double) origH / origW * THUMB_WIDTH);
            if (origW <= THUMB_WIDTH) {
                // 原图已足够小，只记录尺寸不生成缩略图
                return new ThumbnailResult(origW, origH, null);
            }

            BufferedImage thumbnail = new BufferedImage(THUMB_WIDTH, thumbH, BufferedImage.TYPE_INT_RGB);
            Graphics2D g2d = thumbnail.createGraphics();
            try {
                g2d.setRenderingHint(RenderingHints.KEY_INTERPOLATION, RenderingHints.VALUE_INTERPOLATION_BILINEAR);
                g2d.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
                g2d.drawImage(original, 0, 0, THUMB_WIDTH, thumbH, null);
            } finally {
                g2d.dispose();
            }

            String thumbName = baseFileName.replaceFirst("\\.[^.]+$", "_thumb.jpg");
            Path thumbPath = uploadDir.resolve(thumbName);

            try (ByteArrayOutputStream bos = new ByteArrayOutputStream()) {
                ImageIO.write(thumbnail, "jpeg", bos);
                Files.write(thumbPath, bos.toByteArray());
            }

            String thumbnailUrl = accessUrl + thumbName;
            log.info("缩略图生成成功, name={}, size={}x{}", thumbName, THUMB_WIDTH, thumbH);
            return new ThumbnailResult(origW, origH, thumbnailUrl);
        } catch (IOException e) {
            log.error("缩略图生成失败", e);
            return null;
        }
    }
}
