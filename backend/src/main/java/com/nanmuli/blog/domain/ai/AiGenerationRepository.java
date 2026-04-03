package com.nanmuli.blog.domain.ai;

import java.util.List;
import java.util.Optional;

public interface AiGenerationRepository {
    AiGeneration save(AiGeneration generation);

    Optional<AiGeneration> findById(Long id);

    List<AiGeneration> findByArticleId(Long articleId);

    void deleteById(Long id);
}
