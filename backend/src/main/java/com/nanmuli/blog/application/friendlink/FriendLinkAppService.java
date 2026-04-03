package com.nanmuli.blog.application.friendlink;

import com.nanmuli.blog.application.friendlink.dto.FriendLinkDTO;
import com.nanmuli.blog.domain.friendlink.FriendLink;
import com.nanmuli.blog.domain.friendlink.FriendLinkRepository;
import com.nanmuli.blog.shared.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class FriendLinkAppService {

    private final FriendLinkRepository friendLinkRepository;

    @Transactional
    public Long create(FriendLinkDTO dto) {
        FriendLink friendLink = new FriendLink();
        BeanUtils.copyProperties(dto, friendLink);
        friendLinkRepository.save(friendLink);
        return friendLink.getId();
    }

    @Transactional
    public void update(Long id, FriendLinkDTO dto) {
        FriendLink friendLink = friendLinkRepository.findById(id)
                .orElseThrow(() -> new BusinessException("友链不存在"));
        BeanUtils.copyProperties(dto, friendLink);
        friendLink.setId(id);
        friendLinkRepository.save(friendLink);
    }

    @Transactional(readOnly = true)
    public List<FriendLinkDTO> listAllActive() {
        return friendLinkRepository.findAllActive().stream().map(this::toDTO).toList();
    }

    @Transactional(readOnly = true)
    public FriendLinkDTO getById(Long id) {
        FriendLink friendLink = friendLinkRepository.findById(id)
                .orElseThrow(() -> new BusinessException("友链不存在"));
        return toDTO(friendLink);
    }

    @Transactional
    public void delete(Long id) {
        friendLinkRepository.deleteById(id);
    }

    private FriendLinkDTO toDTO(FriendLink friendLink) {
        FriendLinkDTO dto = new FriendLinkDTO();
        BeanUtils.copyProperties(friendLink, dto);
        return dto;
    }
}
