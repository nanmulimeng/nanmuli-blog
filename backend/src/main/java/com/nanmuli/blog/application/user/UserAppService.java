package com.nanmuli.blog.application.user;

import cn.dev33.satoken.stp.StpUtil;
import cn.hutool.crypto.digest.BCrypt;
import com.nanmuli.blog.application.user.command.LoginCommand;
import com.nanmuli.blog.application.user.dto.UserDTO;
import com.nanmuli.blog.domain.user.User;
import com.nanmuli.blog.domain.user.UserRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class UserAppService {

    private final UserRepository userRepository;

    public String login(LoginCommand command) {
        User user = userRepository.findByUsername(command.getUsername())
                .orElseThrow(() -> new BusinessException("用户名或密码错误"));
        if (!BCrypt.checkpw(command.getPassword(), user.getPassword())) {
            throw new BusinessException("用户名或密码错误");
        }
        if (user.getStatus() != 1) {
            throw new BusinessException("账号已被禁用");
        }
        StpUtil.login(user.getId());
        return StpUtil.getTokenValue();
    }

    @Transactional(readOnly = true)
    public UserDTO getCurrentUser() {
        Long userId = StpUtil.getLoginIdAsLong();
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException("用户不存在"));
        UserDTO dto = new UserDTO();
        BeanUtils.copyProperties(user, dto);
        return dto;
    }

    public void logout() {
        StpUtil.logout();
    }
}
