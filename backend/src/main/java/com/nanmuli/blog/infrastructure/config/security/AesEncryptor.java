package com.nanmuli.blog.infrastructure.config.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

@Component
public class AesEncryptor {

    private static final String ALGORITHM = "AES";
    private static final String MARKER = "{AES}";

    private final String secretKey;

    public AesEncryptor(@Value("${blog.security.encryption-key:nanmuli-blog-key}") String secretKey) {
        // 补足/截断为 16 字节 (AES-128)
        byte[] keyBytes = new byte[16];
        byte[] srcBytes = secretKey.getBytes(StandardCharsets.UTF_8);
        System.arraycopy(srcBytes, 0, keyBytes, 0, Math.min(srcBytes.length, 16));
        this.secretKey = new String(keyBytes, StandardCharsets.UTF_8);
    }

    public String encrypt(String plainText) {
        if (plainText == null || plainText.isEmpty()) return plainText;
        if (plainText.startsWith(MARKER)) return plainText; // 已加密
        try {
            SecretKeySpec keySpec = new SecretKeySpec(secretKey.getBytes(StandardCharsets.UTF_8), ALGORITHM);
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.ENCRYPT_MODE, keySpec);
            byte[] encrypted = cipher.doFinal(plainText.getBytes(StandardCharsets.UTF_8));
            return MARKER + Base64.getEncoder().encodeToString(encrypted);
        } catch (Exception e) {
            return plainText; // 加密失败不阻塞业务流程
        }
    }

    public String decrypt(String cipherText) {
        if (cipherText == null || cipherText.isEmpty()) return cipherText;
        if (!cipherText.startsWith(MARKER)) return cipherText; // 明文直接返回
        try {
            String base64 = cipherText.substring(MARKER.length());
            SecretKeySpec keySpec = new SecretKeySpec(secretKey.getBytes(StandardCharsets.UTF_8), ALGORITHM);
            Cipher cipher = Cipher.getInstance(ALGORITHM);
            cipher.init(Cipher.DECRYPT_MODE, keySpec);
            byte[] decrypted = cipher.doFinal(Base64.getDecoder().decode(base64));
            return new String(decrypted, StandardCharsets.UTF_8);
        } catch (Exception e) {
            return cipherText; // 解密失败返回原文
        }
    }
}
