<script setup lang="ts">
import type { Project } from '@/types/project'

const props = defineProps<{
  project: Project
}>()

const emit = defineEmits<{
  click: [id: number]
}>()

function handleClick(): void {
  emit('click', props.project.id)
}

/**
 * 验证URL协议是否安全（只允许http/https）
 */
function isSafeUrl(url: string | undefined): boolean {
  if (!url) return false
  try {
    const urlObj = new URL(url)
    return urlObj.protocol === 'http:' || urlObj.protocol === 'https:'
  } catch {
    return false
  }
}
</script>

<template>
  <article
    class="group overflow-hidden rounded-xl border bg-surface-secondary transition-shadow hover:shadow-lg"
  >
    <div
      v-if="project.cover"
      class="h-48 overflow-hidden bg-surface-tertiary"
      @click="handleClick"
    >
      <img
        :src="project.cover"
        :alt="project.name"
        class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
      />
    </div>

    <div class="p-6">
      <h3
        class="mb-2 cursor-pointer text-xl font-bold text-content-primary group-hover:text-primary"
        @click="handleClick"
      >
        {{ project.name }}
      </h3>

      <p class="mb-4 line-clamp-2 text-sm text-content-secondary">
        {{ project.description }}
      </p>

      <div v-if="project.techStack?.length" class="mb-4 flex flex-wrap gap-2">
        <span
          v-for="tech in project.techStack.slice(0, 5)"
          :key="tech"
          class="rounded bg-primary/10 px-2 py-1 text-xs text-primary"
        >
          {{ tech }}
        </span>
      </div>

      <div class="flex items-center gap-4">
        <a
          v-if="isSafeUrl(project.githubUrl)"
          :href="project.githubUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="text-sm text-content-tertiary hover:text-primary"
          @click.stop
        >
          GitHub
        </a>
        <a
          v-if="isSafeUrl(project.demoUrl)"
          :href="project.demoUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="text-sm text-content-tertiary hover:text-primary"
          @click.stop
        >
          演示
        </a>
        <a
          v-if="isSafeUrl(project.docUrl)"
          :href="project.docUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="text-sm text-content-tertiary hover:text-primary"
          @click.stop
        >
          文档
        </a>
      </div>
    </div>
  </article>
</template>
