package com.nanmuli.blog.infrastructure.persistence.webcollector;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.nanmuli.blog.domain.webcollector.DigestFingerprint;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface DigestFingerprintMapper extends BaseMapper<DigestFingerprint> {

    @Insert("INSERT INTO digest_fingerprint (id, task_id, url_hash, url, title, simhash, digest_date, is_deleted) " +
            "VALUES (#{id}, #{taskId}, #{urlHash}, #{url}, #{title}, #{simhash}, #{digestDate}, false) " +
            "ON CONFLICT (url_hash, digest_date) DO NOTHING")
    int insertIgnoreOnConflict(DigestFingerprint fp);

    /**
     * 批量插入指纹（使用 UNNEST 一次写入多行，减少数据库往返）。
     * 注：MyBatis 动态 SQL foreach 生成多 VALUES 子句，ON CONFLICT 逐行处理。
     */
    @Insert({"<script>",
            "INSERT INTO digest_fingerprint (id, task_id, url_hash, url, title, simhash, digest_date, is_deleted) ",
            "VALUES ",
            "<foreach collection='list' item='fp' separator=','>",
            "(#{fp.id}, #{fp.taskId}, #{fp.urlHash}, #{fp.url}, #{fp.title}, #{fp.simhash}, #{fp.digestDate}, false)",
            "</foreach>",
            " ON CONFLICT (url_hash, digest_date) DO NOTHING",
            "</script>"})
    int batchInsertIgnoreOnConflict(@Param("list") List<DigestFingerprint> fingerprints);
}
