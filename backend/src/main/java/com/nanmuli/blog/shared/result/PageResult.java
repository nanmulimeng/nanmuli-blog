package com.nanmuli.blog.shared.result;

import lombok.Data;

import java.util.List;

@Data
public class PageResult<T> {
    private Long total;
    private Long pages;
    private Long current;
    private Long size;
    private List<T> records;

    public PageResult() {}

    public PageResult(Long total, Long current, Long size, List<T> records) {
        this.total = total;
        this.current = current;
        this.size = size;
        this.records = records;
        this.pages = size == 0 ? 0 : (total + size - 1) / size;
    }
}
