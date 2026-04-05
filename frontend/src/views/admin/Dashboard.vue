<script setup lang="ts">
import { ref, onMounted } from 'vue'

const stats = ref([
  { label: '文章数量', value: 0, icon: 'Document', color: 'text-blue-500', bgColor: 'bg-blue-50' },
  { label: '分类数量', value: 0, icon: 'Folder', color: 'text-green-500', bgColor: 'bg-green-50' },
  { label: '标签数量', value: 0, icon: 'Collection', color: 'text-purple-500', bgColor: 'bg-purple-50' },
  { label: '总阅读量', value: 0, icon: 'View', color: 'text-orange-500', bgColor: 'bg-orange-50' },
])

const recentArticles = ref([])

onMounted(async () => {
  // TODO: 加载统计数据
})
</script>

<template>
  <div>
    <h2 class="mb-6 text-2xl font-bold text-gray-900">仪表盘</h2>

    <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="rounded-xl border bg-white p-6"
      >
        <div class="flex items-center gap-4">
          <div :class="['rounded-lg p-3', stat.bgColor, stat.color]">
            <el-icon :size="24">
              <component :is="stat.icon" />
            </el-icon>
          </div>
          <div>
            <p class="text-sm text-gray-600">{{ stat.label }}</p>
            <p class="text-2xl font-bold text-gray-900">{{ stat.value }}</p>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-8 grid gap-6 lg:grid-cols-2">
      <div class="rounded-xl border bg-white p-6">
        <h3 class="mb-4 text-lg font-semibold text-gray-900">快捷操作</h3>
        <div class="grid grid-cols-2 gap-4">
          <router-link
            to="/admin/article/create"
            class="flex flex-col items-center rounded-lg border p-4 transition-colors hover:border-primary-300 hover:bg-primary-50"
          >
            <el-icon :size="32" class="mb-2 text-primary-600">
              <EditPen />
            </el-icon>
            <span class="text-sm font-medium text-gray-700">写文章</span>
          </router-link>
          <router-link
            to="/admin/daily-log"
            class="flex flex-col items-center rounded-lg border p-4 transition-colors hover:border-primary-300 hover:bg-primary-50"
          >
            <el-icon :size="32" class="mb-2 text-primary-600">
              <Notebook />
            </el-icon>
            <span class="text-sm font-medium text-gray-700">写日志</span>
          </router-link>
          <router-link
            to="/admin/project"
            class="flex flex-col items-center rounded-lg border p-4 transition-colors hover:border-primary-300 hover:bg-primary-50"
          >
            <el-icon :size="32" class="mb-2 text-primary-600">
              <FolderOpened />
            </el-icon>
            <span class="text-sm font-medium text-gray-700">管理项目</span>
          </router-link>
          <router-link
            to="/admin/config"
            class="flex flex-col items-center rounded-lg border p-4 transition-colors hover:border-primary-300 hover:bg-primary-50"
          >
            <el-icon :size="32" class="mb-2 text-primary-600">
              <Setting />
            </el-icon>
            <span class="text-sm font-medium text-gray-700">系统配置</span>
          </router-link>
        </div>
      </div>

      <div class="rounded-xl border bg-white p-6">
        <h3 class="mb-4 text-lg font-semibold text-gray-900">最近文章</h3>
        <el-empty v-if="!recentArticles.length" description="暂无文章" />
        <div v-else class="space-y-4">
          <!-- TODO: 显示最近文章列表 -->
        </div>
      </div>
    </div>
  </div>
</template>
