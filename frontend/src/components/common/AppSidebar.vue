<script setup lang="ts">
import { useRouter } from 'vue-router'
import { markRaw } from 'vue'
import {
  Setting, HomeFilled, Odometer, Document, Notebook,
  Collection, FolderOpened, Trophy, Link
} from '@element-plus/icons-vue'

defineProps<{
  collapsed: boolean
}>()

const router = useRouter()

const menuItems = [
  { path: '/admin', icon: markRaw(Odometer), label: '仪表盘' },
  { path: '/admin/article', icon: markRaw(Document), label: '文章管理' },
  { path: '/admin/daily-log', icon: markRaw(Notebook), label: '日志管理' },
  { path: '/admin/category', icon: markRaw(Collection), label: '分类管理' },
  { path: '/admin/collector', icon: markRaw(Link), label: '内容采集' },
  { path: '/admin/project', icon: markRaw(FolderOpened), label: '项目管理' },
  { path: '/admin/skill', icon: markRaw(Trophy), label: '技能管理' },
  { path: '/admin/config', icon: markRaw(Setting), label: '系统配置' },
]

function isActive(path: string): boolean {
  const currentPath = router.currentRoute.value.path
  // 仪表盘路径 /admin 需要精确匹配，避免所有子路由都高亮
  if (path === '/admin') {
    return currentPath === '/admin' || currentPath === '/admin/'
  }
  return currentPath.startsWith(path)
}
</script>

<template>
  <aside
    class="flex flex-col border-r border-border bg-surface-secondary transition-all duration-300"
    :class="collapsed ? 'w-16' : 'w-64'"
  >
    <div class="flex h-16 items-center justify-center border-b border-border">
      <span v-if="!collapsed" class="text-lg font-bold text-primary">管理后台</span>
      <el-icon v-else :size="24" class="text-primary"><Setting /></el-icon>
    </div>

    <nav class="flex-1 py-4">
      <router-link
        v-for="item in menuItems"
        :key="item.path"
        :to="item.path"
        class="flex items-center px-4 py-3 text-sm transition-colors"
        :class="isActive(item.path) ? 'bg-primary/10 text-primary' : 'text-content-secondary hover:bg-surface-tertiary'"
      >
        <el-icon :size="18">
          <component :is="item.icon" />
        </el-icon>
        <span v-if="!collapsed" class="ml-3">{{ item.label }}</span>
      </router-link>
    </nav>

    <div class="border-t border-border p-4">
      <router-link
        to="/"
        class="flex items-center text-sm text-content-primary hover:text-primary transition-colors"
      >
        <el-icon :size="18"><HomeFilled /></el-icon>
        <span v-if="!collapsed" class="ml-3">返回前台</span>
      </router-link>
    </div>
  </aside>
</template>
