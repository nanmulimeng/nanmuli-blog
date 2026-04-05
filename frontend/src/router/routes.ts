import type { RouteRecordRaw } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'
import BlankLayout from '@/layouts/BlankLayout.vue'

/**
 * 公开路由 - 不需要登录
 */
export const publicRoutes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/home/Index.vue'),
    meta: { layout: DefaultLayout, title: '首页' },
  },
  {
    path: '/article',
    name: 'ArticleList',
    component: () => import('@/views/article/List.vue'),
    meta: { layout: DefaultLayout, title: '文章列表' },
  },
  {
    path: '/article/:slug',
    name: 'ArticleDetail',
    component: () => import('@/views/article/Detail.vue'),
    meta: { layout: DefaultLayout, title: '文章详情' },
  },
  {
    path: '/archive',
    name: 'ArticleArchive',
    component: () => import('@/views/article/Archive.vue'),
    meta: { layout: DefaultLayout, title: '归档' },
  },
  {
    path: '/daily-log',
    name: 'DailyLogList',
    component: () => import('@/views/dailyLog/List.vue'),
    meta: { layout: DefaultLayout, title: '技术日志' },
  },
  {
    path: '/daily-log/:id',
    name: 'DailyLogDetail',
    component: () => import('@/views/dailyLog/Detail.vue'),
    meta: { layout: DefaultLayout, title: '日志详情' },
  },
  {
    path: '/tag',
    name: 'Tag',
    component: () => import('@/views/tag/Index.vue'),
    meta: { layout: DefaultLayout, title: '标签' },
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('@/views/about/Index.vue'),
    meta: { layout: DefaultLayout, title: '关于' },
  },
  {
    path: '/project',
    name: 'Project',
    component: () => import('@/views/project/Index.vue'),
    meta: { layout: DefaultLayout, title: '项目展示' },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { layout: BlankLayout, title: '登录' },
  },
]

/**
 * 管理后台路由 - 需要登录
 */
export const adminRoutes: RouteRecordRaw[] = [
  {
    path: '/admin',
    name: 'AdminDashboard',
    component: () => import('@/views/admin/Dashboard.vue'),
    meta: { layout: AdminLayout, title: '仪表盘', requiresAuth: true },
  },
  {
    path: '/admin/article',
    name: 'AdminArticleList',
    component: () => import('@/views/admin/article/List.vue'),
    meta: { layout: AdminLayout, title: '文章管理', requiresAuth: true },
  },
  {
    path: '/admin/article/create',
    name: 'AdminArticleCreate',
    component: () => import('@/views/admin/article/Create.vue'),
    meta: { layout: AdminLayout, title: '新建文章', requiresAuth: true },
  },
  {
    path: '/admin/article/edit/:id',
    name: 'AdminArticleEdit',
    component: () => import('@/views/admin/article/Edit.vue'),
    meta: { layout: AdminLayout, title: '编辑文章', requiresAuth: true },
  },
  {
    path: '/admin/daily-log',
    name: 'AdminDailyLogList',
    component: () => import('@/views/admin/dailyLog/List.vue'),
    meta: { layout: AdminLayout, title: '日志管理', requiresAuth: true },
  },
  {
    path: '/admin/daily-log/create',
    name: 'AdminDailyLogCreate',
    component: () => import('@/views/admin/dailyLog/Create.vue'),
    meta: { layout: AdminLayout, title: '新建日志', requiresAuth: true },
  },
  {
    path: '/admin/daily-log/edit/:id',
    name: 'AdminDailyLogEdit',
    component: () => import('@/views/admin/dailyLog/Edit.vue'),
    meta: { layout: AdminLayout, title: '编辑日志', requiresAuth: true },
  },
  {
    path: '/admin/tag',
    name: 'AdminTag',
    component: () => import('@/views/admin/tag/Index.vue'),
    meta: { layout: AdminLayout, title: '标签管理', requiresAuth: true },
  },
  {
    path: '/admin/project',
    name: 'AdminProject',
    component: () => import('@/views/admin/project/Index.vue'),
    meta: { layout: AdminLayout, title: '项目管理', requiresAuth: true },
  },
  {
    path: '/admin/skill',
    name: 'AdminSkill',
    component: () => import('@/views/admin/skill/Index.vue'),
    meta: { layout: AdminLayout, title: '技能管理', requiresAuth: true },
  },
  {
    path: '/admin/config',
    name: 'AdminConfig',
    component: () => import('@/views/admin/config/Index.vue'),
    meta: { layout: AdminLayout, title: '系统配置', requiresAuth: true },
  },
]

/**
 * 错误页面路由
 */
export const errorRoutes: RouteRecordRaw[] = [
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFound.vue'),
    meta: { layout: BlankLayout, title: '页面未找到' },
  },
]

/**
 * 所有路由
 */
export const routes: RouteRecordRaw[] = [
  ...publicRoutes,
  ...adminRoutes,
  ...errorRoutes,
]
