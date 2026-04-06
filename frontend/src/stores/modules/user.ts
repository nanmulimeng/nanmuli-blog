import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login, logout, getCurrentUser } from '@/api/auth'
import type { LoginForm, UserInfo } from '@/types/user'
import router from '@/router'

export const useUserStore = defineStore(
  'user',
  () => {
    // Cookie模式：Token由浏览器自动管理，不存储在localStorage
    const isAuthenticated = ref<boolean>(false)
    const userInfo = ref<UserInfo | null>(null)

    const isLoggedIn = computed(() => isAuthenticated.value)

    async function loginAction(form: LoginForm): Promise<void> {
      // Cookie模式：后端设置httpOnly Cookie，前端无需处理Token
      await login(form)

      isAuthenticated.value = true

      // 登录成功后获取用户信息
      try {
        const user = await getCurrentUser()
        userInfo.value = user
      } catch {
        // 即使获取用户信息失败，也不影响登录本身
      }
    }

    async function logoutAction(): Promise<void> {
      try {
        await logout()
      } finally {
        isAuthenticated.value = false
        userInfo.value = null
        // Cookie模式下Token由后端清除，前端无需操作
        router.push('/login')
      }
    }

    function setUserInfo(info: UserInfo): void {
      userInfo.value = info
    }

    // 检查登录状态（页面刷新时调用）
    async function checkAuthStatus(): Promise<boolean> {
      try {
        const user = await getCurrentUser()
        userInfo.value = user
        isAuthenticated.value = true
        return true
      } catch {
        isAuthenticated.value = false
        userInfo.value = null
        return false
      }
    }

    return {
      isAuthenticated,
      userInfo,
      isLoggedIn,
      loginAction,
      logoutAction,
      setUserInfo,
      checkAuthStatus,
    }
  },
  {
    persist: {
      paths: ['isAuthenticated']
    }
  }
)
