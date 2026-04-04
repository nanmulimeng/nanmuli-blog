<script setup lang="ts">
import { useConfigStore } from '@/stores/modules/config'

const configStore = useConfigStore()

const currentYear = new Date().getFullYear()
</script>

<template>
  <footer class="bg-white border-t border-gray-200">
    <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex flex-col md:flex-row items-center justify-between gap-4">
        <!-- Copyright -->
        <div class="text-sm text-gray-500">
          <span>{{ configStore.siteFooter || `© ${currentYear} 我的博客` }}</span>
          <span v-if="configStore.siteIcp" class="ml-2 text-gray-400">| {{ configStore.siteIcp }}</span>
        </div>

        <!-- Social Links -->
        <div class="flex items-center gap-4">
          <a
            v-if="configStore.siteGithub"
            :href="configStore.siteGithub"
            target="_blank"
            rel="noopener noreferrer"
            class="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 hover:bg-gray-200 hover:text-gray-700 transition-colors"
            aria-label="GitHub"
          >
            <el-icon :size="18"><Promotion /></el-icon>
          </a>
          <a
            v-if="configStore.siteEmail"
            :href="`mailto:${configStore.siteEmail}`"
            class="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 hover:bg-gray-200 hover:text-gray-700 transition-colors"
            aria-label="邮箱"
          >
            <el-icon :size="18"><Message /></el-icon>
          </a>
        </div>
      </div>
    </div>
  </footer>
</template>
