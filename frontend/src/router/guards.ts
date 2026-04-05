import type { Router, NavigationGuardNext, RouteLocationNormalized } from 'vue-router'

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
    const token = localStorage.getItem('token')

    // 需要登录的页面
    if (to.meta.requiresAuth && !token) {
      next('/login')
      return
    }

    // 已登录用户访问登录页，重定向到后台
    if (to.path === '/login' && token) {
      next('/admin')
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
