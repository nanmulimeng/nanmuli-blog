package com.nanmuli.blog.interfaces.rest;

import com.nanmuli.blog.application.friendlink.FriendLinkAppService;
import com.nanmuli.blog.application.friendlink.dto.FriendLinkDTO;
import com.nanmuli.blog.shared.result.Result;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "友情链接")
@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class FriendLinkController {

    private final FriendLinkAppService friendLinkAppService;

    @GetMapping("/friend-link/list")
    public Result<List<FriendLinkDTO>> list() {
        return Result.success(friendLinkAppService.listAllActive());
    }

    @PostMapping("/admin/friend-link")
    public Result<Long> create(@Valid @RequestBody FriendLinkDTO dto) {
        return Result.success(friendLinkAppService.create(dto));
    }

    @PutMapping("/admin/friend-link/{id}")
    public Result<Void> update(@PathVariable Long id, @Valid @RequestBody FriendLinkDTO dto) {
        friendLinkAppService.update(id, dto);
        return Result.success();
    }

    @DeleteMapping("/admin/friend-link/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        friendLinkAppService.delete(id);
        return Result.success();
    }
}
