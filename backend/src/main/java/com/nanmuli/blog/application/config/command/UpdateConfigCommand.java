package com.nanmuli.blog.application.config.command;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.io.Serializable;

@Data
public class UpdateConfigCommand implements Serializable {
    private static final long serialVersionUID = 1L;

    @NotNull(message = "配置值不能为null")
    private String value;
}
