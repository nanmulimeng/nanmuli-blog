import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login, logout } from '@/api/auth'
import type { LoginForm, UserInfo } from '@/types/user'
import router from '@/router'

export const useUserStore = defineStore(
  'user',
  () => {
    const token = ref<string | null>(localStorage.getItem('token'))
    const userInfo = ref<UserInfo | null>(null)

    const isLoggedIn = computed(() => !!token.value)

    async function loginAction(form: LoginForm): Promise<void> {
      const result = await login(form)
      token.value = result.token
      userInfo.value = result.userInfo
      localStorage.setItem('token', result.token)
    }

    async function logoutAction(): Promise<void> {
      try {
        await logout()
      } finally {
        token.value = null
        userInfo.value = null
        localStorage.removeItem('token')
        router.push('/login')
      }
    }

    function setUserInfo(info: UserInfo): void {
      userInfo.value = info
    }

    return {
      token,
      userInfo,
      isLoggedIn,
      loginAction,
      logoutAction,
      setUserInfo,
    }
  },
  {
    persist: {
      paths: ['token'],
    },
  }
)
