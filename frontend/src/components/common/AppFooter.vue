<script setup lang="ts">
import { useConfigStore } from '@/stores/modules/config'

const configStore = useConfigStore()
const currentYear = new Date().getFullYear()

const footerLinks = [
  { label: '首页', path: '/' },
  { label: '文章', path: '/article' },
  { label: '日志', path: '/daily-log' },
  { label: '项目', path: '/project' },
  { label: '关于', path: '/about' },
]
</script>

<template>
  <footer class="relative overflow-hidden border-t border-border">
    <!-- Background Decoration -->
    <div class="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-primary/10" />
    <div class="absolute bottom-0 left-1/2 -translate-x-1/2 h-px w-1/2 bg-gradient-to-r from-transparent via-primary to-transparent" />

    <div class="relative mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
      <!-- Main Footer Content -->
      <div class="grid gap-12 lg:grid-cols-4">
        <!-- Brand -->
        <div class="lg:col-span-2">
          <div class="flex items-center gap-3 mb-4">
            <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-cyan-500 text-white shadow-lg dark:from-blue-500 dark:to-blue-500">
              <el-icon class="text-xl"><Document /></el-icon>
            </div>
            <span class="text-xl font-bold text-content-primary">
              {{ configStore.siteName || 'Nanmuli' }}
            </span>
          </div>
          <p class="max-w-sm text-content-secondary leading-relaxed">
            {{ configStore.siteDescription || '记录技术成长，分享学习心得，探索代码世界的无限可能' }}
          </p>

          <!-- Social Links -->
          <div class="mt-6 flex items-center gap-3">
            <a
              v-if="configStore.siteGithub"
              :href="configStore.siteGithub"
              target="_blank"
              rel="noopener noreferrer"
              class="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-tertiary text-content-secondary transition-all hover:bg-content-primary hover:text-surface-secondary"
              aria-label="GitHub"
            >
              <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
            </a>
            <a
              v-if="configStore.siteEmail"
              :href="`mailto:${configStore.siteEmail}`"
              class="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-tertiary text-content-secondary transition-all hover:bg-primary hover:text-white"
              aria-label="邮箱"
            >
              <el-icon class="text-lg"><Message /></el-icon>
            </a>
          </div>
        </div>

        <!-- Quick Links -->
        <div>
          <h3 class="text-sm font-semibold text-content-primary mb-4">快速链接</h3>
          <nav class="flex flex-wrap gap-4">
            <router-link
              v-for="link in footerLinks"
              :key="link.path"
              :to="link.path"
              class="text-content-secondary hover:text-primary transition-colors"
            >
              {{ link.label }}
            </router-link>
          </nav>
        </div>

        <!-- Admin -->
        <div>
          <h3 class="text-sm font-semibold text-content-primary mb-4">管理</h3>
          <nav class="flex flex-wrap gap-4">
            <router-link
              to="/admin"
              class="text-content-secondary hover:text-primary transition-colors"
            >
              管理后台
            </router-link>
            <router-link
              to="/admin/article"
              class="text-content-secondary hover:text-primary transition-colors"
            >
              发布文章
            </router-link>
          </nav>
        </div>
      </div>

      <!-- Bottom Bar -->
      <div class="mt-12 pt-8 border-t border-border">
        <div class="flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-content-tertiary">
          <p>
            {{ configStore.siteFooter || `© ${currentYear} Nanmuli Blog. All rights reserved.` }}
            <span v-if="configStore.siteIcp" class="ml-2">| {{ configStore.siteIcp }}</span>
          </p>
          <p class="flex items-center gap-1">
            Made with
            <el-icon class="text-primary"><StarFilled /></el-icon>
            and code
          </p>
        </div>
      </div>
    </div>
  </footer>
</template>
