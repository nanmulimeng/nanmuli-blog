<script setup lang="ts">
import AppHeader from '@/components/common/AppHeader.vue'
import AppFooter from '@/components/common/AppFooter.vue'
</script>

<template>
  <div class="flex min-h-screen flex-col bg-surface-primary transition-colors duration-300">
    <AppHeader />
    <main class="flex-1 pt-16">
      <router-view />
    </main>
    <AppFooter />
  </div>
</template>
