package com.nanmuli.blog;

import cn.hutool.crypto.digest.BCrypt;
import org.junit.jupiter.api.Test;

public class PasswordGenTest {
    @Test
    public void generatePassword() {
        String password = "admin123";
        String hash = BCrypt.hashpw(password, BCrypt.gensalt());
        System.out.println("Password: " + password);
        System.out.println("Hash: " + hash);

        // Verify
        boolean check = BCrypt.checkpw(password, hash);
        System.out.println("Verify: " + check);
    }
}
