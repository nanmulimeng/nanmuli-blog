package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.webcollector.DigestFingerprint;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DigestFingerprintMapper extends BaseMapper<DigestFingerprint> {

    @Insert("INSERT INTO digest_fingerprint (task_id, url_hash, url, title, simhash, digest_date, is_deleted) " +
            "VALUES (#{taskId}, #{urlHash}, #{url}, #{title}, #{simhash}, #{digestDate}, false) " +
            "ON CONFLICT (url_hash, digest_date) DO NOTHING")
    int insertIgnoreOnConflict(DigestFingerprint fp);
}
