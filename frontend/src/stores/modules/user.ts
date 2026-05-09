import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login, logout, getCurrentUser } from '@/api/auth'
import type { LoginForm, UserInfo } from '@/types/user'
import router from '@/router'

export const useUserStore = defineStore(
  'user',
  () => {
    const isAuthenticated = ref<boolean>(false)
    const userInfo = ref<UserInfo | null>(null)

    const isLoggedIn = computed(() => isAuthenticated.value)

    async function loginAction(form: LoginForm): Promise<void> {
      await login(form)

      isAuthenticated.value = true

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
        router.push('/login')
      }
    }

    function setUserInfo(info: UserInfo): void {
      userInfo.value = info
    }

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

    // 跨 Tab 同步：监听 localStorage 变化，当其他 Tab 登出时同步清除状态
    if (typeof window !== 'undefined') {
      window.addEventListener('storage', (e) => {
        if (e.key === 'user') {
          try {
            const parsed = e.newValue ? JSON.parse(e.newValue) : null
            if (!parsed?.isAuthenticated) {
              isAuthenticated.value = false
              userInfo.value = null
            }
          } catch {
            isAuthenticated.value = false
          }
        }
      })
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
