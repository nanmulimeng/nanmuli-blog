<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center bg-surface-tertiary">
    <div class="text-center">
      <h1 class="text-9xl font-bold text-content-tertiary/50">404</h1>
      <h2 class="mt-4 text-2xl font-semibold text-content-primary">页面未找到</h2>
      <p class="mt-2 text-content-secondary">抱歉，您访问的页面不存在</p>
      <button
        class="mt-8 rounded-lg bg-primary px-6 py-3 text-white transition-colors hover:bg-primary-dark"
        @click="router.push('/')"
      >
        返回首页
      </button>
    </div>
  </div>
</template>
