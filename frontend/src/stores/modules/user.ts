import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login, logout, getCurrentUser } from '@/api/auth'
import type { LoginForm, UserInfo } from '@/types/user'
import router from '@/router'

export const useUserStore = defineStore(
  'user',
  () => {
    const token = ref<string | null>(localStorage.getItem('token'))
    const userInfo = ref<UserInfo | null>(null)

    const isLoggedIn = computed(() => !!token.value)

    async function loginAction(form: LoginForm): Promise<void> {
      console.log('[Login] 开始登录...')
      const tokenValue = await login(form)
      console.log('[Login] 获取token成功:', tokenValue.substring(0, 10) + '...')

      token.value = tokenValue
      localStorage.setItem('token', tokenValue)
      console.log('[Login] token已保存到localStorage')

      // 登录成功后获取用户信息
      try {
        console.log('[Login] 获取用户信息...')
        const user = await getCurrentUser()
        userInfo.value = user
        console.log('[Login] 获取用户信息成功:', user.username)
      } catch (e) {
        console.error('[Login] 获取用户信息失败:', e)
        // 即使获取用户信息失败，也不影响登录本身
      }
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
