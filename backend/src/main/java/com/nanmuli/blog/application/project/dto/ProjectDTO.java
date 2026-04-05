package com.nanmuli.blog.application.project.dto;

import com.fasterxml.jackson.annotation.JsonFormat;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class ProjectDTO implements Serializable {
    private static final long serialVersionUID = 1L;
    private Long id;

    @NotBlank(message = "项目名称不能为空")
    @Size(max = 100, message = "项目名称长度不能超过100字符")
    private String name;

    @Pattern(regexp = "^[a-z0-9-]+$", message = "项目标识只能包含小写字母、数字和连字符")
    private String slug;

    private String description;
    private String cover;
    private List<String> screenshots;
    private List<String> techStack;

    @Pattern(regexp = "^(https?://.*)?$", message = "GitHub链接必须是http或https协议")
    private String githubUrl;

    @Pattern(regexp = "^(https?://.*)?$", message = "演示链接必须是http或https协议")
    private String demoUrl;

    @Pattern(regexp = "^(https?://.*)?$", message = "文档链接必须是http或https协议")
    private String docUrl;

    private Integer sort;
    private Integer status;

    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate startDate;

    @JsonFormat(pattern = "yyyy-MM-dd")
    private LocalDate endDate;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;

    @AssertTrue(message = "结束时间不能早于开始时间")
    public boolean isDateRangeValid() {
        if (startDate == null || endDate == null) {
            return true;
        }
        return !endDate.isBefore(startDate);
    }
}
