package com.nanmuli.blog.domain.webcollector;

import com.baomidou.mybatisplus.annotation.TableName;
import com.nanmuli.blog.shared.domain.BaseAggregateRoot;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;

@Getter
@Setter
@EqualsAndHashCode(callSuper = false)
@TableName("digest_fingerprint")
public class DigestFingerprint extends BaseAggregateRoot<Long> {
    private static final long serialVersionUID = 1L;

    private Long taskId;
    private String urlHash;
    private String url;
    private String title;
    private Long simhash;
    private LocalDate digestDate;
}
