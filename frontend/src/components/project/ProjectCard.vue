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
</script>

<template>
  <article
    class="group overflow-hidden rounded-xl border bg-white transition-shadow hover:shadow-lg"
  >
    <div
      v-if="project.cover"
      class="h-48 overflow-hidden bg-gray-100"
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
        class="mb-2 cursor-pointer text-xl font-bold text-gray-900 group-hover:text-blue-600"
        @click="handleClick"
      >
        {{ project.name }}
      </h3>

      <p class="mb-4 line-clamp-2 text-sm text-gray-600">
        {{ project.description }}
      </p>

      <div v-if="project.techStack?.length" class="mb-4 flex flex-wrap gap-2">
        <span
          v-for="tech in project.techStack.slice(0, 5)"
          :key="tech"
          class="rounded bg-blue-50 px-2 py-1 text-xs text-blue-600"
        >
          {{ tech }}
        </span>
      </div>

      <div class="flex items-center gap-4">
        <a
          v-if="project.githubUrl"
          :href="project.githubUrl"
          target="_blank"
          class="text-sm text-gray-500 hover:text-blue-600"
          @click.stop
        >
          GitHub
        </a>
        <a
          v-if="project.demoUrl"
          :href="project.demoUrl"
          target="_blank"
          class="text-sm text-gray-500 hover:text-blue-600"
          @click.stop
        >
          演示
        </a>
        <a
          v-if="project.docUrl"
          :href="project.docUrl"
          target="_blank"
          class="text-sm text-gray-500 hover:text-blue-600"
          @click.stop
        >
          文档
        </a>
      </div>
    </div>
  </article>
</template>
