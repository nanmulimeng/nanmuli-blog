package com.nanmuli.blog.interfaces.rest;

import cn.dev33.satoken.annotation.SaCheckPermission;
import com.nanmuli.blog.application.file.FileAppService;
import com.nanmuli.blog.application.file.command.UploadFileCommand;
import com.nanmuli.blog.application.file.dto.FileDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@Tag(name = "文件管理")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class FileController {

    private final FileAppService fileAppService;

    @SaCheckPermission("file:upload")
    @PostMapping("/admin/file/upload")
    public Result<FileDTO> upload(@RequestParam("file") MultipartFile file) {
        UploadFileCommand command = new UploadFileCommand();
        command.setOriginalName(file.getOriginalFilename());
        command.setContentType(file.getContentType());
        command.setFileSize(file.getSize());
        try {
            command.setContent(file.getBytes());
        } catch (Exception e) {
            return Result.error(400, "文件读取失败");
        }
        return Result.success(fileAppService.upload(command));
    }

    @GetMapping("/file/{id}")
    public Result<FileDTO> getById(@PathVariable Long id) {
        return Result.success(fileAppService.getById(id));
    }
}
