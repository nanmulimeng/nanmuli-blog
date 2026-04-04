<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCategoryList } from '@/api/category'
import type { Category } from '@/types/category'

const router = useRouter()
const loading = ref(false)
const categories = ref<Category[]>([])

const categoryIcons: Record<string, string> = {
  backend: 'Cpu',
  frontend: 'Monitor',
  database: 'Coin',
  devops: 'SetUp',
  'daily-log': 'Timer',
  projects: 'OfficeBuilding'
}

async function fetchCategories(): Promise<void> {
  loading.value = true
  try {
    const res = await getCategoryList()
    categories.value = res
  } finally {
    loading.value = false
  }
}

onMounted(fetchCategories)
</script>

<template>
  <div class="category-page">
    <!-- Page Header -->
    <section class="bg-gray-50 py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center">
        <h1 class="text-3xl font-bold text-gray-900">文章分类</h1>
        <p class="mt-2 text-gray-500">按主题浏览文章</p>
      </div>
    </section>

    <!-- Categories Grid -->
    <section class="py-12">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <!-- Loading -->
        <div v-if="loading" class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div v-for="i in 6" :key="i" class="bg-white rounded-xl p-6 border border-gray-100">
            <el-skeleton :rows="2" animated />
          </div>
        </div>

        <!-- Categories -->
        <div v-else class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="category in categories"
            :key="category.id"
            class="group cursor-pointer bg-white rounded-xl p-6 border border-gray-100 shadow-sm transition-all duration-150 hover:shadow-lg hover:-translate-y-0.5"
            @click="router.push(`/article?category=${category.id}`)"
          >
            <div class="flex items-start justify-between">
              <div class="flex items-center gap-4">
                <div
                  class="w-12 h-12 rounded-xl flex items-center justify-center text-white text-xl transition-transform duration-150 group-hover:scale-110"
                  :style="{ backgroundColor: category.color || '#0284c7' }"
                >
                  <el-icon>
                    <component :is="categoryIcons[category.slug] || 'Folder'" />
                  </el-icon>
                </div>
                <div>
                  <h3 class="text-lg font-semibold text-gray-900 group-hover:text-primary-600 transition-colors">
                    {{ category.name }}
                  </h3>
                  <p class="text-sm text-gray-500">{{ category.articleCount }} 篇文章</p>
                </div>
              </div>
              <el-icon class="text-gray-300 group-hover:text-primary-600 transition-colors">
                <ArrowRight />
              </el-icon>
            </div>

            <p v-if="category.description" class="mt-4 text-sm text-gray-600">
              {{ category.description }}
            </p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
