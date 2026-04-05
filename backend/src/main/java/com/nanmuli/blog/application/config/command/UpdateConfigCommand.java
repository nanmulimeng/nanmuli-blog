package com.nanmuli.blog.application.config.command;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.io.Serializable;

@Data
public class UpdateConfigCommand implements Serializable {
    private static final long serialVersionUID = 1L;

    @NotBlank(message = "配置值不能为空")
    private String value;
}
