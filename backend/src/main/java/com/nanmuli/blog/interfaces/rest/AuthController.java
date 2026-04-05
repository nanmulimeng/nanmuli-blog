package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.user.UserAppService;
import com.nanmuli.blog.application.user.command.LoginCommand;
import com.nanmuli.blog.application.user.dto.UserDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@Tag(name = "认证管理")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class AuthController {

    private final UserAppService userAppService;

    @PostMapping("/auth/login")
    public Result<String> login(@Valid @RequestBody LoginCommand command) {
        String token = userAppService.login(command);
        return Result.success(token);
    }

    @GetMapping("/auth/info")
    public Result<UserDTO> info() {
        return Result.success(userAppService.getCurrentUser());
    }

    @PostMapping("/auth/logout")
    public Result<Void> logout() {
        userAppService.logout();
        return Result.success();
    }

    // TODO: 临时密码重置端点，测试完成后删除
    @PostMapping("/auth/reset-password")
    public Result<Void> resetPassword(@RequestParam String username, @RequestParam String password) {
        userAppService.resetPassword(username, password);
        return Result.success();
    }
}
