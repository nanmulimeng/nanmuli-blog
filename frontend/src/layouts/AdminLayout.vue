<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/modules/user'
import AppSidebar from '@/components/common/AppSidebar.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isCollapsed = ref(false)

onMounted(() => {
  if (!userStore.isLoggedIn) {
    router.push('/login')
  }
})
</script>

<template>
  <div class="flex h-screen bg-gray-100">
    <AppSidebar :collapsed="isCollapsed" />
    <div class="flex flex-1 flex-col overflow-hidden">
      <header class="flex h-16 items-center justify-between border-b bg-white px-6">
        <div class="flex items-center gap-4">
          <button
            class="rounded p-2 text-gray-600 hover:bg-gray-100"
            @click="isCollapsed = !isCollapsed"
          >
            <el-icon><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
          </button>
          <h1 class="text-lg font-semibold text-gray-800">{{ route.meta.title || '管理后台' }}</h1>
        </div>
        <div class="flex items-center gap-4">
          <span class="text-sm text-gray-600">{{ userStore.userInfo?.nickname }}</span>
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
