package com.nanmuli.blog.infrastructure.config.security;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AesEncryptorTest {

    @Test
    void rejectsKnownDefaultEncryptionKey() {
        assertThatThrownBy(() -> new AesEncryptor("nanmuli-blog-key"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("blog.security.encryption-key");
    }

    @Test
    void rejectsBlankOrShortEncryptionKey() {
        assertThatThrownBy(() -> new AesEncryptor(""))
                .isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> new AesEncryptor("short"))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void encryptsAndDecryptsWithStrongKey() {
        AesEncryptor encryptor = new AesEncryptor("test-encryption-key");

        String encrypted = encryptor.encrypt("secret-value");

        assertThat(encrypted).startsWith("{AES}");
        assertThat(encryptor.decrypt(encrypted)).isEqualTo("secret-value");
    }
}
