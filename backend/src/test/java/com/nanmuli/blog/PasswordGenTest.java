package com.nanmuli.blog;

import cn.hutool.crypto.digest.BCrypt;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

public class PasswordGenTest {
    @Test
    public void generatedPasswordHashCanBeVerified() {
        String password = "admin123";
        String hash = BCrypt.hashpw(password, BCrypt.gensalt());

        assertTrue(BCrypt.checkpw(password, hash));
    }
}
