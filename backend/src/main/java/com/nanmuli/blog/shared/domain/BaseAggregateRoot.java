package com.nanmuli.blog.shared.domain;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableLogic;
import lombok.Getter;

import java.io.Serializable;
import java.time.LocalDateTime;

@Getter
public abstract class BaseAggregateRoot<ID extends Serializable> implements Serializable {
    private static final long serialVersionUID = 1L;

    @TableId(type = IdType.ASSIGN_ID)
    protected ID id;

    @TableField(fill = FieldFill.INSERT)
    protected LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    protected LocalDateTime updatedAt;

    @TableLogic
    @TableField(fill = FieldFill.INSERT)
    protected Boolean isDeleted;

    public void setId(ID id) {
        this.id = id;
    }

    public ID getId() {
        return id;
    }

    public boolean isNew() {
        return id == null;
    }
}
