<script setup lang="ts">
import { computed, defineAsyncComponent, type AsyncComponentLoader } from 'vue'
import { useRoute } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'

const route = useRoute()

type LayoutLoader = AsyncComponentLoader
const asyncLayoutCache = new WeakMap<LayoutLoader, ReturnType<typeof defineAsyncComponent>>()

const layoutComponent = computed(() => {
  const layout = route.meta.layout
  if (typeof layout === 'function') {
    const loader = layout as LayoutLoader
    let cached = asyncLayoutCache.get(loader)
    if (!cached) {
      const asyncComp = defineAsyncComponent(loader)
      asyncLayoutCache.set(loader, asyncComp)
      cached = asyncComp
    }
    return cached
  }
  return DefaultLayout
})
</script>

<template>
  <component :is="layoutComponent" />
</template>

<style>
#app {
  min-height: 100vh;
}
</style>
