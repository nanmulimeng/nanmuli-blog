<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getPublicDigestList } from '@/api/collector'
import type { DigestListItem } from '@/types/collector'
import { PAGE_SIZE } from '@/constants/api'

const router = useRouter()
const loading = ref(false)
const digests = ref<DigestListItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(PAGE_SIZE.DIGEST)

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res = await getPublicDigestList(currentPage.value, pageSize.value)
    digests.value = res.records
    total.value = res.total
  } catch {
    // 日报服务不可用时静默处理
  } finally {
    loading.value = false
  }
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchData()
}

function handleView(row: DigestListItem): void {
  if (row.digest_date) {
    router.push(`/digest/${row.digest_date}`)
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return dateStr.slice(0, 10)
}

onMounted(fetchData)
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-content-primary">技术日报</h1>
      <p class="mt-2 text-content-secondary">每日精选技术资讯、开源动态与开发工具</p>
    </div>

    <div v-loading="loading">
      <div v-if="digests.length" class="space-y-4">
        <div
          v-for="item in digests"
          :key="item.id"
          class="group cursor-pointer rounded-xl border border-border bg-surface-secondary p-5 shadow-sm transition-all hover:border-primary/30 hover:shadow-md"
          @click="handleView(item)"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-3">
                <span class="text-sm font-medium text-primary">{{ formatDate(item.digest_date) }}</span>
                <el-tag v-if="item.status === 3" type="success" size="small">已完成</el-tag>
              </div>
              <h3 v-if="item.ai_title" class="mt-2 text-lg font-semibold text-content-primary group-hover:text-primary transition-colors">
                {{ item.ai_title }}
              </h3>
              <p v-if="item.highlight" class="mt-1 text-sm text-content-secondary line-clamp-2">
                {{ item.highlight }}
              </p>
              <div v-if="item.ai_tags?.length" class="mt-3 flex flex-wrap gap-1.5">
                <el-tag v-for="tag in item.ai_tags.slice(0, 5)" :key="tag" size="small" effect="plain">
                  {{ tag }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="!loading && digests.length === 0" class="py-20 text-center">
        <el-empty description="暂无日报数据" />
      </div>
    </div>

    <div v-if="total > pageSize" class="mt-6 flex justify-center">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :pager-count="7"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>
