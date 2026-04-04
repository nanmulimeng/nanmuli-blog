<script setup lang="ts">
import { useConfigStore } from '@/stores/modules/config'
import { onMounted } from 'vue'

const configStore = useConfigStore()

onMounted(() => {
  configStore.loadConfig()
})
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
    <div class="rounded-xl border bg-white p-8">
      <div class="mb-8 text-center">
        <el-avatar :size="120" :src="configStore.siteAvatar" class="mb-4" />
        <h1 class="text-3xl font-bold text-gray-900">关于我</h1>
      </div>

      <div class="markdown-body" v-html="configStore.siteAbout || '暂无内容'" />

      <div class="mt-8 flex justify-center gap-4">
        <a
          v-if="configStore.siteGithub"
          :href="configStore.siteGithub"
          target="_blank"
          rel="noopener noreferrer"
          class="flex items-center gap-2 rounded-lg bg-gray-900 px-4 py-2 text-white transition-colors hover:bg-gray-800"
        >
          <el-icon><Link /></el-icon>
          <span>GitHub</span>
        </a>
        <a
          v-if="configStore.siteEmail"
          :href="`mailto:${configStore.siteEmail}`"
          class="flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-white transition-colors hover:bg-primary-700"
        >
          <el-icon><Message /></el-icon>
          <span>联系我</span>
        </a>
      </div>
    </div>
  </div>
</template>
