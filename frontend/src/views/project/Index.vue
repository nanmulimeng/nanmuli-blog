<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getProjectList } from '@/api/project'
import type { Project } from '@/types/project'

const projects = ref<Project[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const selectedProject = ref<Project | null>(null)

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

/**
 * 格式化项目时间线
 */
function formatProjectDate(startDate?: string, endDate?: string): string {
  if (!startDate) return '时间未知'
  const start = new Date(startDate).getFullYear()
  if (!endDate) return `${start} 至今`
  const end = new Date(endDate).getFullYear()
  return start === end ? `${start}` : `${start} - ${end}`
}

/**
 * 判断项目是否进行中
 */
function isOngoing(endDate?: string): boolean {
  if (!endDate) return true
  return new Date(endDate) > new Date()
}

/**
 * 打开项目详情弹窗
 */
function openProjectDetail(project: Project): void {
  selectedProject.value = project
  dialogVisible.value = true
}
</script>

<template>
  <div class="project-page">
    <!-- Page Header -->
    <section class="py-12">
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
          <div v-for="i in 6" :key="i" class="bg-surface-primary rounded-xl overflow-hidden border border-border">
            <div class="aspect-video bg-surface-primary" />
            <div class="p-5">
              <el-skeleton :rows="3" animated />
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
            class="group bg-surface-primary rounded-xl overflow-hidden border border-border shadow-sm transition-all duration-150 hover:shadow-lg cursor-pointer"
            @click="openProjectDetail(project)"
          >
            <!-- Cover -->
            <div class="aspect-video bg-surface-primary relative overflow-hidden">
              <img
                v-if="project.cover"
                :src="project.cover"
                :alt="project.name"
                class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
              >
              <div v-else class="w-full h-full flex items-center justify-center text-content-tertiary/50">
                <el-icon :size="48"><OfficeBuilding /></el-icon>
              </div>
              <!-- Status Badge -->
              <div class="absolute top-3 right-3">
                <span
                  class="px-2 py-1 rounded-full text-xs font-medium"
                  :class="isOngoing(project.endDate)
                    ? 'bg-success/90 text-white'
                    : 'bg-content-tertiary/70 text-white'"
                >
                  {{ isOngoing(project.endDate) ? '进行中' : '已完成' }}
                </span>
              </div>
            </div>

            <!-- Content -->
            <div class="p-5">
              <!-- Title & Date -->
              <div class="flex items-start justify-between gap-2 mb-2">
                <h3 class="text-lg font-semibold text-content-primary line-clamp-1">{{ project.name }}</h3>
                <span class="text-xs text-content-tertiary whitespace-nowrap">
                  {{ formatProjectDate(project.startDate, project.endDate) }}
                </span>
              </div>

              <p class="text-sm text-content-secondary line-clamp-2 mb-4">
                {{ project.description }}
              </p>

              <!-- Tech Stack -->
              <div class="flex flex-wrap gap-1.5 mb-4">
                <span
                  v-for="tech in project.techStack?.slice(0, 5)"
                  :key="tech"
                  class="px-2 py-0.5 rounded-md bg-primary/10 text-primary text-xs font-medium"
                >
                  {{ tech }}
                </span>
                <span
                  v-if="project.techStack?.length > 5"
                  class="px-2 py-0.5 rounded-md bg-surface-secondary text-content-tertiary text-xs"
                >
                  +{{ project.techStack.length - 5 }}
                </span>
              </div>

              <!-- Links -->
              <div class="flex flex-wrap gap-3">
                <a
                  v-if="isSafeUrl(project.demoUrl)"
                  :href="project.demoUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-primary text-white text-sm font-medium transition-colors hover:bg-primary/90"
                  @click.stop
                >
                  <el-icon><Link /></el-icon> 演示
                </a>
                <a
                  v-if="isSafeUrl(project.githubUrl)"
                  :href="project.githubUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-secondary text-content-secondary text-sm transition-colors hover:bg-surface-tertiary hover:text-content-primary"
                  @click.stop
                >
                  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                  </svg>
                  源码
                </a>
                <a
                  v-if="isSafeUrl(project.docUrl)"
                  :href="project.docUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-border text-content-secondary text-sm transition-colors hover:border-primary hover:text-primary"
                  @click.stop
                >
                  <el-icon><Document /></el-icon> 文档
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Project Detail Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="selectedProject?.name"
      width="800px"
      class="theme-dialog"
      destroy-on-close
    >
      <div v-if="selectedProject" class="space-y-6">
        <!-- Cover -->
        <div class="aspect-video rounded-xl overflow-hidden bg-surface-secondary">
          <img
            v-if="selectedProject.cover"
            :src="selectedProject.cover"
            :alt="selectedProject.name"
            class="w-full h-full object-cover"
          >
          <div v-else class="w-full h-full flex items-center justify-center text-content-tertiary/50">
            <el-icon :size="64"><OfficeBuilding /></el-icon>
          </div>
        </div>

        <!-- Meta Info -->
        <div class="flex flex-wrap items-center gap-3">
          <span
            class="px-3 py-1 rounded-full text-sm font-medium"
            :class="isOngoing(selectedProject.endDate)
              ? 'bg-success/10 text-success'
              : 'bg-content-tertiary/10 text-content-tertiary'"
          >
            {{ isOngoing(selectedProject.endDate) ? '进行中' : '已完成' }}
          </span>
          <span class="flex items-center gap-1 text-sm text-content-tertiary">
            <el-icon><Calendar /></el-icon>
            {{ formatProjectDate(selectedProject.startDate, selectedProject.endDate) }}
          </span>
        </div>

        <!-- Description -->
        <p class="text-content-secondary leading-relaxed">
          {{ selectedProject.description }}
        </p>

        <!-- Tech Stack -->
        <div>
          <h4 class="text-sm font-semibold text-content-primary mb-3">技术栈</h4>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="tech in selectedProject.techStack"
              :key="tech"
              class="px-3 py-1.5 rounded-lg bg-primary/10 text-primary text-sm font-medium"
            >
              {{ tech }}
            </span>
          </div>
        </div>

        <!-- Screenshots -->
        <div v-if="selectedProject.screenshots?.length">
          <h4 class="text-sm font-semibold text-content-primary mb-3">项目截图</h4>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div
              v-for="(screenshot, index) in selectedProject.screenshots"
              :key="index"
              class="aspect-video rounded-lg overflow-hidden bg-surface-secondary cursor-pointer hover:ring-2 hover:ring-primary transition-all"
              @click="window.open(screenshot, '_blank')"
            >
              <img :src="screenshot" class="w-full h-full object-cover" :alt="`截图 ${index + 1}`">
            </div>
          </div>
        </div>

        <!-- Links -->
        <div class="flex flex-wrap gap-3 pt-4 border-t border-border">
          <a
            v-if="isSafeUrl(selectedProject.demoUrl)"
            :href="selectedProject.demoUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-white font-medium transition-colors hover:bg-primary/90"
          >
            <el-icon><Link /></el-icon> 在线演示
          </a>
          <a
            v-if="isSafeUrl(selectedProject.githubUrl)"
            :href="selectedProject.githubUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-secondary text-content-secondary font-medium transition-colors hover:bg-surface-tertiary hover:text-content-primary"
          >
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            查看源码
          </a>
          <a
            v-if="isSafeUrl(selectedProject.docUrl)"
            :href="selectedProject.docUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-content-secondary font-medium transition-colors hover:border-primary hover:text-primary"
          >
            <el-icon><Document /></el-icon> 开发文档
          </a>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
