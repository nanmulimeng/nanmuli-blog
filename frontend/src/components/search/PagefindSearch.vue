<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'

// Pagefind 类型定义
interface PagefindResult {
  data(): Promise<{
    meta: { title: string }
    excerpt: string
    url: string
  }>
}

interface PagefindInstance {
  init(): Promise<void>
  search(query: string): Promise<{
    results: PagefindResult[]
  }>
}

const searchQuery = ref('')
const searchResults = ref<Array<{ title: string; excerpt: string; url: string }>>([])
const isSearching = ref(false)
const showResults = ref(false)

// Pagefind 实例
let pagefind: PagefindInstance | null = null

async function initPagefind(): Promise<void> {
  try {
    // 动态导入 Pagefind
    const module = await import('/pagefind/pagefind.js')
    pagefind = module.default || module
    await pagefind.init()
  } catch (error) {
    console.warn('Pagefind 初始化失败:', error)
  }
}

async function handleSearch(): Promise<void> {
  if (!searchQuery.value.trim() || !pagefind) {
    searchResults.value = []
    return
  }

  isSearching.value = true
  try {
    const results = await pagefind.search(searchQuery.value)
    searchResults.value = await Promise.all(
      results.results.slice(0, 10).map(async (result: PagefindResult) => {
        const data = await result.data()
        return {
          title: data.meta.title || '无标题',
          excerpt: data.excerpt,
          url: data.url,
        }
      })
    )
    showResults.value = true
  } finally {
    isSearching.value = false
  }
}

function handleBlur(): void {
  // 延迟隐藏以允许点击结果
  setTimeout(() => {
    showResults.value = false
  }, 200)
}

function handleFocus(): void {
  if (searchResults.value.length > 0) {
    showResults.value = true
  }
}

onMounted(() => {
  nextTick(() => {
    initPagefind()
  })
})
</script>

<template>
  <div class="relative">
    <div class="flex items-center gap-2">
      <el-input
        v-model="searchQuery"
        placeholder="搜索文章..."
        class="w-64"
        @keyup.enter="handleSearch"
        @focus="handleFocus"
        @blur="handleBlur"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
        <template #append>
          <el-button :loading="isSearching" @click="handleSearch"> 搜索 </el-button>
        </template>
      </el-input>
    </div>

    <!-- 搜索结果下拉框 -->
    <div
      v-if="showResults && searchResults.length > 0"
      class="absolute top-full z-50 mt-2 w-96 rounded-xl border bg-white p-4 shadow-lg"
    >
      <div class="mb-2 text-sm text-gray-500">
        找到 {{ searchResults.length }} 个结果
      </div>
      <div class="max-h-96 space-y-3 overflow-y-auto">
        <a
          v-for="result in searchResults"
          :key="result.url"
          :href="result.url"
          class="block rounded-lg p-3 transition-colors hover:bg-gray-50"
        >
          <div class="mb-1 font-medium text-gray-900">{{ result.title }}</div>
          <div class="line-clamp-2 text-sm text-gray-600" v-html="result.excerpt" />
        </a>
      </div>
    </div>

    <!-- 无结果提示 -->
    <div
      v-else-if="showResults && !isSearching && searchQuery"
      class="absolute top-full z-50 mt-2 w-96 rounded-xl border bg-white p-4 shadow-lg"
    >
      <div class="text-center text-gray-500">未找到相关结果</div>
    </div>
  </div>
</template>
