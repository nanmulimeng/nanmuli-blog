package com.nanmuli.blog.infrastructure.config.security;

import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;

class ProductionConfigHardeningTest {

    @Test
    void productionYamlRequiresEncryptionKeyEnvironmentVariable() throws Exception {
        String prodYaml = new ClassPathResource("application-prod.yml")
                .getContentAsString(StandardCharsets.UTF_8);

        assertThat(prodYaml).contains("encryption-key: ${BLOG_SECURITY_ENCRYPTION_KEY}");
        assertThat(prodYaml).doesNotContain("BLOG_SECURITY_ENCRYPTION_KEY:nanmuli-blog-key");
    }
}
