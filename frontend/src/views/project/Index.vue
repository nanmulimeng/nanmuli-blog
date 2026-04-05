<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getProjectList } from '@/api/project'
import type { Project } from '@/types/project'

const projects = ref<Project[]>([])
const loading = ref(false)

async function fetchProjects(): Promise<void> {
  loading.value = true
  try {
    const res = await getProjectList()
    projects.value = res
  } finally {
    loading.value = false
  }
}

onMounted(fetchProjects)
</script>

<template>
  <div class="project-page">
    <!-- Page Header -->
    <section class="bg-surface-tertiary py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-content-primary">项目展示</h1>
        <p class="mt-2 text-content-secondary">个人开源项目与作品</p>
      </div>
    </section>

    <!-- Projects Grid -->
    <section class="py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="bg-surface-secondary rounded-xl overflow-hidden border border-border">
            <div class="aspect-video bg-surface-tertiary" />
            <div class="p-5">
              <el-skeleton :rows="2" animated />
            </div>
          </div>
        </div>

        <!-- Empty -->
        <div v-else-if="projects.length === 0" class="text-center py-20">
          <el-icon :size="64" class="text-content-tertiary/30 mb-4"><OfficeBuilding /></el-icon>
          <p class="text-content-tertiary">暂无项目</p>
        </div>

        <!-- Projects -->
        <div v-else class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="project in projects"
            :key="project.id"
            class="group bg-surface-secondary rounded-xl overflow-hidden border border-border shadow-sm transition-all duration-150 hover:shadow-lg"
          >
            <!-- Cover -->
            <div class="aspect-video bg-surface-tertiary relative overflow-hidden">
              <img
                v-if="project.cover"
                :src="project.cover"
                :alt="project.name"
                class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
              >
              <div v-else class="w-full h-full flex items-center justify-center text-content-tertiary/50">
                <el-icon :size="48"><OfficeBuilding /></el-icon>
              </div>
            </div>

            <!-- Content -->
            <div class="p-5">
              <h3 class="text-lg font-semibold text-content-primary mb-2">{{ project.name }}</h3>

              <p class="text-sm text-content-secondary line-clamp-2 mb-4">
                {{ project.description }}
              </p>

              <!-- Tech Stack -->
              <div class="flex flex-wrap gap-2 mb-4">
                <span
                  v-for="tech in project.techStack?.slice(0, 4)"
                  :key="tech"
                  class="px-2 py-1 bg-surface-tertiary rounded text-xs text-content-secondary"
                >
                  {{ tech }}
                </span>
              </div>

              <!-- Links -->
              <div class="flex gap-4">
                <a
                  v-if="project.demoUrl"
                  :href="project.demoUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-sm text-primary hover:text-primary-light flex items-center gap-1"
                  @click.stop
                >
                  <el-icon><Link /></el-icon> 演示
                </a>
                <a
                  v-if="project.githubUrl"
                  :href="project.githubUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-sm text-content-secondary hover:text-content-primary flex items-center gap-1"
                  @click.stop
                >
                  <el-icon><Promotion /></el-icon> GitHub
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
