package com.nanmuli.blog.infrastructure.config.security;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

@Slf4j
@Component
public class AesEncryptor {

    private static final String MARKER = "{AES}";
    private static final String TRANSFORMATION_GCM = "AES/GCM/NoPadding";
    private static final String TRANSFORMATION_LEGACY_ECB = "AES";
    private static final int GCM_IV_LENGTH = 12;
    private static final int GCM_TAG_LENGTH_BITS = 128;

    private final SecretKeySpec keySpec;
    private final SecureRandom random = new SecureRandom();

    public AesEncryptor(@Value("${blog.security.encryption-key:local-dev-encryption-key}") String secretKey) {
        if (isUnsafeKey(secretKey)) {
            throw new IllegalStateException("blog.security.encryption-key must be a non-default secret with at least 16 characters; set BLOG_SECURITY_ENCRYPTION_KEY (or blog.security.encryption-key in dev) to a strong value");
        }
        // 补足/截断为 16 字节 (AES-128)
        byte[] keyBytes = new byte[16];
        byte[] srcBytes = secretKey.getBytes(StandardCharsets.UTF_8);
        System.arraycopy(srcBytes, 0, keyBytes, 0, Math.min(srcBytes.length, 16));
        this.keySpec = new SecretKeySpec(keyBytes, "AES");
    }

    private boolean isUnsafeKey(String value) {
        if (value == null || value.isBlank() || value.length() < 16) {
            return true;
        }
        String normalized = value.trim();
        return "nanmuli-blog-key".equals(normalized)
                // B07-01: 源码公开的默认占位 key 不得用于任何环境
                || "local-dev-encryption-key".equals(normalized)
                || normalized.startsWith("your_")
                || normalized.startsWith("sk-your-");
    }

    public String encrypt(String plainText) {
        if (plainText == null || plainText.isEmpty()) return plainText;
        if (plainText.startsWith(MARKER)) return plainText; // 已加密
        try {
            // B07-02: AES/GCM 带随机 IV 与认证 tag，取代不安全的 ECB
            byte[] iv = new byte[GCM_IV_LENGTH];
            random.nextBytes(iv);
            Cipher cipher = Cipher.getInstance(TRANSFORMATION_GCM);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec, new GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv));
            byte[] cipherText = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));
            byte[] combined = new byte[iv.length + cipherText.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(cipherText, 0, combined, iv.length, cipherText.length);
            return MARKER + Base64.getEncoder().encodeToString(combined);
        } catch (Exception e) {
            // B07-03: 加密失败不得回退明文，否则敏感配置明文落库
            throw new IllegalStateException("AES encryption failed", e);
        }
    }

    public String decrypt(String cipherText) {
        if (cipherText == null || cipherText.isEmpty() || !cipherText.startsWith(MARKER)) {
            return cipherText; // 明文直接返回
        }
        byte[] combined;
        try {
            combined = Base64.getDecoder().decode(cipherText.substring(MARKER.length()));
        } catch (IllegalArgumentException e) {
            log.warn("[AesEncryptor] Invalid base64 ciphertext, returning as-is");
            return cipherText;
        }
        // 新格式 GCM（前 12 byte 为随机 IV），优先尝试
        if (combined.length > GCM_IV_LENGTH) {
            try {
                byte[] iv = new byte[GCM_IV_LENGTH];
                System.arraycopy(combined, 0, iv, 0, GCM_IV_LENGTH);
                byte[] cipherPart = new byte[combined.length - GCM_IV_LENGTH];
                System.arraycopy(combined, GCM_IV_LENGTH, cipherPart, 0, cipherPart.length);
                Cipher cipher = Cipher.getInstance(TRANSFORMATION_GCM);
                cipher.init(Cipher.DECRYPT_MODE, keySpec, new GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv));
                return new String(cipher.doFinal(cipherPart), StandardCharsets.UTF_8);
            } catch (Exception ignored) {
                // 不是 GCM 密文，落到旧 ECB 兼容分支
            }
        }
        // B07-02 兼容：旧 ECB 密文（升级前加密的配置）仍可解密，逐步由 GCM 替代
        try {
            Cipher cipher = Cipher.getInstance(TRANSFORMATION_LEGACY_ECB);
            cipher.init(Cipher.DECRYPT_MODE, keySpec);
            return new String(cipher.doFinal(combined), StandardCharsets.UTF_8);
        } catch (Exception e) {
            log.warn("[AesEncryptor] Decryption failed, returning ciphertext: {}", e.getMessage());
            return cipherText;
        }
    }
}
