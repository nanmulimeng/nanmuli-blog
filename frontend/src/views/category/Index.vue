<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCategoryList } from '@/api/category'
import type { Category } from '@/types/category'

const router = useRouter()
const loading = ref(false)
const categories = ref<Category[]>([])

async function fetchCategories(): Promise<void> {
  loading.value = true
  try {
    categories.value = await getCategoryList()
  } finally {
    loading.value = false
  }
}

onMounted(fetchCategories)
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
    <h1 class="mb-8 text-3xl font-bold text-gray-900">文章分类</h1>

    <div v-if="loading" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <el-skeleton v-for="i in 6" :key="i" :rows="2" animated />
    </div>

    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="category in categories"
        :key="category.id"
        class="cursor-pointer rounded-xl border bg-white p-6 transition-shadow hover:shadow-lg"
        @click="router.push(`/article?category=${category.id}`)"
      >
        <div class="flex items-center gap-3">
          <el-icon v-if="category.icon" :size="24" :style="{ color: category.color }">
            <component :is="category.icon" />
          </el-icon>
          <h3 class="text-lg font-semibold text-gray-900">{{ category.name }}</h3>
        </div>
        <p v-if="category.description" class="mt-2 text-sm text-gray-600">
          {{ category.description }}
        </p>
        <div class="mt-4 flex items-center justify-between">
          <span class="text-sm text-gray-500">{{ category.articleCount }} 篇文章</span>
          <el-icon class="text-gray-400"><ArrowRight /></el-icon>
        </div>
      </div>
    </div>
  </div>
</template>
