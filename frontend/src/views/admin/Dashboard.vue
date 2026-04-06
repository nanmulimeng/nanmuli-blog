<script setup lang="ts">
import { ref, onMounted, markRaw } from 'vue'
import { useRouter } from 'vue-router'
import { Document, FolderOpened, View, User, EditPen, Notebook, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getDashboardStats, getRecentArticles } from '@/api/dashboard'
import type { Article } from '@/types/article'

const router = useRouter()
const loading = ref(false)

interface StatItem {
  label: string
  value: number
  icon: any
}

const stats = ref<StatItem[]>([
  { label: '文章数量', value: 0, icon: markRaw(Document) },
  { label: '项目数量', value: 0, icon: markRaw(FolderOpened) },
  { label: '访问量', value: 0, icon: markRaw(View) },
  { label: '访客数', value: 0, icon: markRaw(User) },
])

const recentArticles = ref<Article[]>([])

async function fetchStats() {
  try {
    const data = await getDashboardStats()
    stats.value[0].value = data.articleCount || 0
    stats.value[1].value = data.projectCount || 0
    stats.value[2].value = data.visitCount || 0      // 访问量（PV）
    stats.value[3].value = data.visitorCount || 0    // 访客数（UV）
  } catch (error: any) {
    ElMessage.error(error?.message || '加载统计数据失败')
  }
}

async function fetchRecentArticles() {
  try {
    recentArticles.value = await getRecentArticles(5)
  } catch (error: any) {
    ElMessage.error(error?.message || '加载最近文章失败')
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
  })
}

function getStatusType(status: number): '' | 'success' | 'info' | 'warning' | 'danger' {
  switch (status) {
    case 1: return 'success'
    case 2: return 'warning'
    case 3: return 'info'
    default: return ''
  }
}

function getStatusText(status: number): string {
  switch (status) {
    case 1: return '已发布'
    case 2: return '草稿'
    case 3: return '回收站'
    default: return '未知'
  }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([fetchStats(), fetchRecentArticles()])
  loading.value = false
})
</script>

<template>
  <div>
    <h2 class="mb-6 text-2xl font-bold text-content-primary">仪表盘</h2>

    <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="rounded-xl border border-border bg-surface-secondary p-6 shadow-sm transition-all hover:shadow-md"
      >
        <div class="flex items-center gap-4">
          <div class="rounded-lg bg-primary/10 p-3 text-primary">
            <el-icon :size="24">
              <component :is="stat.icon" />
            </el-icon>
          </div>
          <div>
            <p class="text-sm text-content-secondary">{{ stat.label }}</p>
            <p class="text-2xl font-bold text-content-primary">{{ stat.value }}</p>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-8 grid gap-6 lg:grid-cols-2">
      <div class="rounded-xl border border-border bg-surface-secondary p-6">
        <h3 class="mb-4 text-lg font-semibold text-content-primary">快捷操作</h3>
        <div class="grid grid-cols-2 gap-4">
          <router-link
            to="/admin/article/create"
            class="flex flex-col items-center rounded-lg border border-border p-4 transition-colors hover:border-primary hover:bg-primary/5"
          >
            <el-icon :size="32" class="mb-2 text-primary">
              <EditPen />
            </el-icon>
            <span class="text-sm font-medium text-content-secondary">写文章</span>
          </router-link>
          <router-link
            to="/admin/daily-log/create"
            class="flex flex-col items-center rounded-lg border border-border p-4 transition-colors hover:border-primary hover:bg-primary/5"
          >
            <el-icon :size="32" class="mb-2 text-primary">
              <Notebook />
            </el-icon>
            <span class="text-sm font-medium text-content-secondary">写日志</span>
          </router-link>
          <router-link
            to="/admin/project"
            class="flex flex-col items-center rounded-lg border border-border p-4 transition-colors hover:border-primary hover:bg-primary/5"
          >
            <el-icon :size="32" class="mb-2 text-primary">
              <FolderOpened />
            </el-icon>
            <span class="text-sm font-medium text-content-secondary">管理项目</span>
          </router-link>
          <router-link
            to="/admin/config"
            class="flex flex-col items-center rounded-lg border border-border p-4 transition-colors hover:border-primary hover:bg-primary/5"
          >
            <el-icon :size="32" class="mb-2 text-primary">
              <Setting />
            </el-icon>
            <span class="text-sm font-medium text-content-secondary">系统配置</span>
          </router-link>
        </div>
      </div>

      <div class="rounded-xl border border-border bg-surface-secondary p-6">
        <h3 class="mb-4 text-lg font-semibold text-content-primary">最近文章</h3>
        <el-empty v-if="!recentArticles.length" description="暂无文章" />
        <div v-else class="space-y-3">
          <div
            v-for="article in recentArticles"
            :key="article.id"
            class="flex cursor-pointer items-center justify-between rounded-lg p-3 transition-colors hover:bg-surface-tertiary"
            @click="router.push(`/admin/article/edit/${article.id}`)"
          >
            <div class="flex-1 min-w-0 mr-4">
              <p class="truncate font-medium text-content-primary">{{ article.title }}</p>
              <p class="text-xs text-content-tertiary">{{ formatDate(article.createTime) }}</p>
            </div>
            <el-tag :type="getStatusType(article.status)" size="small">
              {{ getStatusText(article.status) }}
            </el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
