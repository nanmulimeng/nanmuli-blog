package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.nanmuli.blog.domain.webcollector.DigestFingerprint;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;

@Repository
@RequiredArgsConstructor
public class DigestFingerprintRepositoryImpl {

    private final DigestFingerprintMapper fingerprintMapper;

    public void save(DigestFingerprint fp) {
        if (fp.isNew()) {
            fingerprintMapper.insert(fp);
        } else {
            fingerprintMapper.updateById(fp);
        }
    }

    public void saveAll(List<DigestFingerprint> fingerprints) {
        for (DigestFingerprint fp : fingerprints) {
            fingerprintMapper.insertIgnoreOnConflict(fp);
        }
    }

    public List<DigestFingerprint> findByDigestDateAfter(LocalDate since) {
        LambdaQueryWrapper<DigestFingerprint> wrapper = new LambdaQueryWrapper<>();
        wrapper.ge(DigestFingerprint::getDigestDate, since)
               .eq(DigestFingerprint::getIsDeleted, false)
               .orderByDesc(DigestFingerprint::getDigestDate);
        return fingerprintMapper.selectList(wrapper);
    }

    public void deleteByDigestDateBefore(LocalDate before) {
        LambdaQueryWrapper<DigestFingerprint> wrapper = new LambdaQueryWrapper<>();
        wrapper.lt(DigestFingerprint::getDigestDate, before)
               .eq(DigestFingerprint::getIsDeleted, false);
        fingerprintMapper.delete(wrapper);
    }
}
