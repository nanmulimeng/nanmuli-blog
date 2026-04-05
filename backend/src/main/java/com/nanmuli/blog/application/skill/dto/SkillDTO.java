package com.nanmuli.blog.application.skill.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import com.fasterxml.jackson.databind.ser.std.ToStringSerializer;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
public class SkillDTO implements Serializable {
    private static final long serialVersionUID = 1L;

    @JsonSerialize(using = ToStringSerializer.class)
    private Long id;

    @NotBlank(message = "技能名称不能为空")
    @Size(max = 50, message = "技能名称长度不能超过50字符")
    private String name;

    @NotBlank(message = "技能分类不能为空")
    private String category;

    @NotNull(message = "熟练度不能为空")
    @Min(value = 1, message = "熟练度最小值为1")
    @Max(value = 5, message = "熟练度最大值为5")
    private Integer proficiency;

    private String icon;

    @Pattern(regexp = "^#[0-9A-Fa-f]{6}$", message = "颜色格式必须为十六进制，如#FF5733")
    private String color;

    private String description;
    private Integer sort;
    private Integer status;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
