package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.incrementer.IdentifierGenerator;
import com.nanmuli.blog.domain.webcollector.DigestFingerprint;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;

@Repository
@RequiredArgsConstructor
public class DigestFingerprintRepositoryImpl {

    private final DigestFingerprintMapper fingerprintMapper;
    private final IdentifierGenerator identifierGenerator;

    public void save(DigestFingerprint fp) {
        if (fp.isNew()) {
            fingerprintMapper.insert(fp);
        } else {
            fingerprintMapper.updateById(fp);
        }
    }

    /**
     * 批量保存指纹，分批执行避免单次 SQL 过长。
     * 每批最多 100 条，使用批量 INSERT + ON CONFLICT DO NOTHING。
     */
    public void saveAll(List<DigestFingerprint> fingerprints) {
        if (fingerprints == null || fingerprints.isEmpty()) {
            return;
        }
        // 手写批量 INSERT 绕过 MyBatis-Plus 的 ASSIGN_ID 自动填充，需预先分配雪花 id（B09-01 修复）
        for (DigestFingerprint fp : fingerprints) {
            if (fp.getId() == null) {
                fp.setId(identifierGenerator.nextId(fp).longValue());
            }
        }
        int batchSize = 100;
        for (int i = 0; i < fingerprints.size(); i += batchSize) {
            List<DigestFingerprint> batch = fingerprints.subList(i, Math.min(i + batchSize, fingerprints.size()));
            fingerprintMapper.batchInsertIgnoreOnConflict(batch);
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
