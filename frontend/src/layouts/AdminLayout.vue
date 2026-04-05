<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/modules/user'
import { getCurrentUser } from '@/api/auth'
import { initTheme } from '@/styles/themes'
import AppSidebar from '@/components/common/AppSidebar.vue'
import ThemeSwitcher from '@/components/common/ThemeSwitcher.vue'

const route = useRoute()
const userStore = useUserStore()
const isCollapsed = ref(false)
const isLoading = ref(false)

onMounted(async () => {
  // 初始化主题
  initTheme()

  // 路由守卫已处理登录检查，这里只负责获取用户信息
  // 如果已有token但没有用户信息，获取用户信息
  if (userStore.isLoggedIn && !userStore.userInfo) {
    isLoading.value = true
    try {
      const userInfo = await getCurrentUser()
      userStore.setUserInfo(userInfo)
    } catch {
      // 获取失败，清除登录状态并跳转登录页
      userStore.logoutAction()
    } finally {
      isLoading.value = false
    }
  }
})
</script>

<template>
  <div class="flex h-screen bg-surface-primary transition-colors duration-300">
    <AppSidebar :collapsed="isCollapsed" />
    <div class="flex flex-1 flex-col overflow-hidden">
      <header class="flex h-16 items-center justify-between border-b border-border bg-surface-secondary px-6">
        <div class="flex items-center gap-4">
          <button
            class="rounded p-2 text-content-secondary hover:bg-surface-tertiary transition-colors"
            @click="isCollapsed = !isCollapsed"
          >
            <el-icon><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
          </button>
          <h1 class="text-lg font-semibold text-content-primary">{{ route.meta.title || '管理后台' }}</h1>
        </div>
        <div class="flex items-center gap-4">
          <ThemeSwitcher />
          <span class="text-sm text-content-secondary">{{ userStore.userInfo?.nickname }}</span>
          <el-dropdown>
            <el-avatar :size="32" :src="userStore.userInfo?.avatar" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="userStore.logoutAction()">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      <main class="flex-1 overflow-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>
