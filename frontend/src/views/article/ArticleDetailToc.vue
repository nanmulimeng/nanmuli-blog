<script setup lang="ts">
import { ref } from 'vue'

export interface TocItem {
  id: string
  text: string
  level: number
}

defineProps<{
  toc: TocItem[]
  activeHeading: string
  isMobile: boolean
}>()

const emit = defineEmits<{
  (e: 'select', index: number): void
}>()

const showMobileToc = ref(false)
const tocNavRef = ref<HTMLElement | null>(null)

function handleMobileSelect(index: number): void {
  emit('select', index)
  showMobileToc.value = false
}

function handleDesktopSelect(index: number): void {
  emit('select', index)
}
</script>

<template>
  <!-- Mobile TOC Button -->
  <button
    v-if="isMobile && toc.length > 0"
    class="fixed bottom-6 right-6 z-50 p-3 rounded-full bg-primary text-white shadow-lg shadow-primary/30 hover:bg-primary-light transition-all"
    @click="showMobileToc = true"
  >
    <el-icon><List /></el-icon>
  </button>

  <!-- Mobile TOC Drawer -->
  <el-drawer
    v-model="showMobileToc"
    title="目录"
    direction="btt"
    size="50%"
    :with-header="true"
  >
    <nav class="space-y-1 max-h-[60vh] overflow-y-auto">
      <a
        v-for="(item, index) in toc"
        :key="item.id"
        :href="`#${item.id}`"
        class="block py-3 text-sm transition-all rounded-lg px-3 border-b border-surface-tertiary last:border-0"
        :class="[
          item.level === 1 ? 'text-content-secondary font-medium' : 'text-content-tertiary',
          item.level === 2 ? 'pl-6' : '',
          item.level === 3 ? 'pl-9' : '',
          activeHeading === item.id
            ? 'bg-primary/10 text-primary'
            : 'hover:bg-surface-tertiary'
        ]"
        @click.prevent="handleMobileSelect(index)"
      >
        {{ item.text }}
      </a>
    </nav>
  </el-drawer>

  <!-- Sidebar TOC -->
  <div class="hidden lg:block lg:col-span-4">
    <div class="sticky top-28 space-y-6">
      <!-- TOC Card -->
      <div class="glass-card rounded-2xl p-6">
        <h3 class="flex items-center gap-2 text-sm font-semibold text-content-primary mb-4">
          <el-icon><List /></el-icon>
          目录
        </h3>
        <nav ref="tocNavRef" class="space-y-1 max-h-[calc(100vh-300px)] overflow-y-auto scrollbar-hide">
          <a
            v-for="(item, index) in toc"
            :key="item.id"
            :href="`#${item.id}`"
            class="block py-2 text-sm transition-all rounded-lg px-3"
            :class="[
              item.level === 1 ? 'text-content-secondary font-medium' : 'text-content-tertiary',
              item.level === 2 ? 'pl-6' : '',
              item.level === 3 ? 'pl-9' : '',
              activeHeading === item.id
                ? 'bg-primary/10 text-primary'
                : 'hover:bg-surface-tertiary'
            ]"
            @click.prevent="handleDesktopSelect(index)"
          >
            {{ item.text }}
          </a>
        </nav>
      </div>

      <!-- Quick Actions -->
      <div class="glass-card rounded-2xl p-6">
        <h3 class="text-sm font-semibold text-content-primary mb-4">
          快速操作
        </h3>
        <div class="space-y-2">
          <router-link
            to="/article"
            class="flex items-center gap-3 p-3 rounded-xl text-sm text-content-secondary transition-all hover:bg-surface-tertiary"
          >
            <el-icon><ArrowLeft /></el-icon>
            返回文章列表
          </router-link>
          <router-link
            to="/"
            class="flex items-center gap-3 p-3 rounded-xl text-sm text-content-secondary transition-all hover:bg-surface-tertiary"
          >
            <el-icon><HomeFilled /></el-icon>
            回到首页
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
</style>
