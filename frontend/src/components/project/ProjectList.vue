<script setup lang="ts">
import ProjectCard from './ProjectCard.vue'
import type { Project } from '@/types/project'

defineProps<{
  projects: Project[]
  loading?: boolean
}>()

const emit = defineEmits<{
  click: [id: number]
}>()

function handleProjectClick(id: number): void {
  emit('click', id)
}
</script>

<template>
  <div>
    <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <el-skeleton v-for="i in 6" :key="i" animated :rows="4" />
    </div>

    <div v-else-if="projects.length === 0" class="py-12 text-center text-gray-500">
      暂无项目
    </div>

    <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <ProjectCard
        v-for="project in projects"
        :key="project.id"
        :project="project"
        @click="handleProjectClick"
      />
    </div>
  </div>
</template>
