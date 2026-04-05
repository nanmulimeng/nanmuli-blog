<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{
  collapsed: boolean
}>()

const router = useRouter()

const menuItems = [
  { path: '/admin', icon: 'Odometer', label: '仪表盘' },
  { path: '/admin/article', icon: 'Document', label: '文章管理' },
  { path: '/admin/daily-log', icon: 'Notebook', label: '日志管理' },
  { path: '/admin/tag', icon: 'Collection', label: '标签管理' },
  { path: '/admin/project', icon: 'FolderOpened', label: '项目管理' },
  { path: '/admin/skill', icon: 'Trophy', label: '技能管理' },
  { path: '/admin/config', icon: 'Setting', label: '系统配置' },
]

function isActive(path: string): boolean {
  return router.currentRoute.value.path.startsWith(path)
}
</script>

<template>
  <aside
    class="flex flex-col border-r bg-white transition-all duration-300"
    :class="collapsed ? 'w-16' : 'w-64'"
  >
    <div class="flex h-16 items-center justify-center border-b">
      <span v-if="!collapsed" class="text-lg font-bold text-primary-600">管理后台</span>
      <el-icon v-else :size="24" class="text-primary-600"><Setting /></el-icon>
    </div>

    <nav class="flex-1 py-4">
      <router-link
        v-for="item in menuItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center px-4 py-3 text-sm transition-colors"
        :class="isActive(item.path) ? 'bg-primary-50 text-primary-600' : 'text-gray-600 hover:bg-gray-50'"
      >
        <el-icon :size="18">
          <component :is="item.icon" />
        </el-icon>
        <span v-if="!collapsed" class="ml-3">{{ item.label }}</span>
      </router-link>
    </nav>

    <div class="border-t p-4">
      <router-link
        to="/"
        class="flex items-center text-sm text-gray-600 hover:text-primary-600"
      >
        <el-icon :size="18"><HomeFilled /></el-icon>
        <span v-if="!collapsed" class="ml-3">返回前台</span>
      </router-link>
    </div>
  </aside>
</template>
