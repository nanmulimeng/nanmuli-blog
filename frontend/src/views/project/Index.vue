<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getProjectList } from '@/api/project'
import { formatDate } from '@/utils/format'
import type { Project } from '@/types/project'

const loading = ref(false)
const projects = ref<Project[]>([])

async function fetchProjects(): Promise<void> {
  loading.value = true
  try {
    projects.value = await getProjectList()
  } finally {
    loading.value = false
  }
}

onMounted(fetchProjects)
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
    <h1 class="mb-8 text-3xl font-bold text-gray-900">项目展示</h1>

    <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <el-skeleton v-for="i in 6" :key="i" :rows="3" animated />
    </div>

    <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="project in projects"
        :key="project.id"
        class="overflow-hidden rounded-xl border bg-white transition-shadow hover:shadow-lg"
      >
        <div class="h-48 overflow-hidden bg-gray-100">
          <img
            v-if="project.cover"
            :src="project.cover"
            :alt="project.name"
            class="h-full w-full object-cover"
          />
          <div v-else class="flex h-full items-center justify-center text-gray-400">
            <el-icon :size="48"><FolderOpened /></el-icon>
          </div>
        </div>

        <div class="p-6">
          <h3 class="text-xl font-semibold text-gray-900">{{ project.name }}</h3>
          <p class="mt-2 line-clamp-2 text-sm text-gray-600">{{ project.description }}</p>

          <div v-if="project.techStack?.length" class="mt-4 flex flex-wrap gap-2">
            <span
              v-for="tech in project.techStack"
              :key="tech"
              class="rounded bg-gray-100 px-2 py-1 text-xs text-gray-600"
            >
              {{ tech }}
            </span>
          </div>

          <div class="mt-4 flex items-center gap-4">
            <a
              v-if="project.githubUrl"
              :href="project.githubUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm text-primary-600 hover:underline"
            >
              GitHub
            </a>
            <a
              v-if="project.demoUrl"
              :href="project.demoUrl"
              target="_blank"
              rel="noopener noreferrer"
              class="text-sm text-primary-600 hover:underline"
            >
              演示
            </a>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
