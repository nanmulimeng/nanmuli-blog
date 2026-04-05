import type { Router, NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useUserStore } from '@/stores/modules/user'

/**
 * 设置路由守卫
 * @param router - Vue Router 实例
 */
export function setupRouterGuards(router: Router): void {
  // 全局前置守卫
  router.beforeEach((
    to: RouteLocationNormalized,
    _from: RouteLocationNormalized,
    next: NavigationGuardNext
  ) => {
    // 使用 store 获取登录状态，确保与组件层状态一致
    const userStore = useUserStore()
    const isLoggedIn = userStore.isLoggedIn

    // 需要登录的页面
    if (to.meta.requiresAuth && !isLoggedIn) {
      // 保存目标路径，登录后跳转回去
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }

    // 已登录用户访问登录页，重定向到后台（或原目标页）
    if (to.path === '/login' && isLoggedIn) {
      const redirect = to.query.redirect as string
      next(redirect || '/admin')
      return
    }

    next()
  })

  // 全局后置钩子 - 设置页面标题
  router.afterEach((to: RouteLocationNormalized) => {
    if (to.meta.title) {
      document.title = `${to.meta.title} - Nanmuli Blog`
    }
  })

  // 错误处理
  router.onError((error) => {
    console.error('路由错误:', error)
  })
}
