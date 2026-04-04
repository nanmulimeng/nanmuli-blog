import { computed } from 'vue'
import { useUserStore } from '@/stores/modules/user'
import type { LoginForm } from '@/types/user'

/**
 * 认证相关组合式函数
 */
export function useAuth() {
  const userStore = useUserStore()

  const isLoggedIn = computed(() => userStore.isLoggedIn)
  const userInfo = computed(() => userStore.userInfo)
  const token = computed(() => userStore.token)

  async function login(form: LoginForm): Promise<void> {
    await userStore.loginAction(form)
  }

  async function logout(): Promise<void> {
    await userStore.logoutAction()
  }

  return {
    isLoggedIn,
    userInfo,
    token,
    login,
    logout,
  }
}
