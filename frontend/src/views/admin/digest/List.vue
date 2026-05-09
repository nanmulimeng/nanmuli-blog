<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getDigestList, triggerDigest } from '@/api/collector'
import type { DigestListItem } from '@/types/collector'
import { CollectTaskStatusMap } from '@/types/collector'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Calendar, View, Promotion } from '@element-plus/icons-vue'
import { usePolling } from '@/composables/usePolling'
import { PAGE_SIZE, POLLING_INTERVAL, DELAY } from '@/constants/api'

const router = useRouter()
const loading = ref(false)
const digests = ref<DigestListItem[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(PAGE_SIZE.DIGEST)
const triggerLoading = ref(false)

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res = await getDigestList(currentPage.value, pageSize.value)
    digests.value = res.records
    total.value = res.total
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
    router.push(`/admin/digest/${row.digest_date}`)
  } else {
    router.push(`/admin/digest/task/${row.id}`)
  }
}

async function handleTrigger(): Promise<void> {
  try {
    // 检测今天是否已有日报
    const today = new Date().toISOString().slice(0, 10)
    const todayDigest = digests.value.find(d => d.digest_date?.startsWith(today) && d.status === 3)

    if (todayDigest) {
      await ElMessageBox.confirm(
        '今日已有日报，确定要强制重新生成吗？',
        '重新生成',
        { type: 'warning', confirmButtonText: '强制重新生成', cancelButtonText: '取消' }
      )
      triggerLoading.value = true
      await triggerDigest(true)
    } else {
      await ElMessageBox.confirm('确定要手动触发生成今日技术日报吗？', '提示', { type: 'info' })
      triggerLoading.value = true
      await triggerDigest()
    }

    ElMessage.success('日报生成已触发，请稍后刷新查看')
    setTimeout(() => fetchData(), DELAY.DIGEST_REFRESH)
  } catch (error: unknown) {
    if (error === 'cancel' || (error instanceof Error && error.message === 'cancel')) return
  } finally {
    triggerLoading.value = false
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  return dateStr.slice(0, 10)
}

function hasActiveTasks(): boolean {
  return digests.value.some(d => d.status === 0 || d.status === 1 || d.status === 2)
}

// 使用 usePolling 替代手动 setInterval 轮询
const { start: startPolling } = usePolling(fetchData, POLLING_INTERVAL.DIGEST_STATUS, {
  immediate: false,
  condition: () => hasActiveTasks() && !loading.value,
})

onMounted(() => {
  fetchData()
  startPolling()
})
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <el-icon :size="24" class="text-primary"><Calendar /></el-icon>
        <h2 class="text-xl font-bold text-content-primary">技术日报</h2>
      </div>
      <el-button type="primary" :icon="Promotion" :loading="triggerLoading" @click="handleTrigger">
        生成日报
      </el-button>
    </div>

    <el-table v-loading="loading" :data="digests" border>
      <el-table-column label="日期" width="130">
        <template #default="{ row }">
          <span class="font-medium text-content-primary">{{ formatDate(row.digest_date) }}</span>
        </template>
      </el-table-column>

      <el-table-column label="标题" min-width="260">
        <template #default="{ row }">
          <div v-if="row.ai_title" class="text-sm font-medium text-content-primary">
            {{ row.ai_title }}
          </div>
          <div v-else-if="row.status === 0 || row.status === 1 || row.status === 2" class="text-content-tertiary">生成中...</div>
          <div v-else-if="row.error_message" class="text-sm text-error/80 truncate" :title="row.error_message">
            {{ row.error_message }}
          </div>
          <div v-else class="text-content-tertiary">-</div>
          <div v-if="row.highlight" class="mt-1 truncate text-xs text-content-secondary" :title="row.highlight">
            {{ row.highlight }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="CollectTaskStatusMap[row.status]?.type || 'info'" size="small">
            <div class="flex items-center gap-1">
              <el-icon v-if="row.status === 1 || row.status === 2" :size="12" class="animate-spin">
                <Refresh />
              </el-icon>
              {{ row.status_label || CollectTaskStatusMap[row.status]?.label || '未知' }}
            </div>
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="标签" width="200">
        <template #default="{ row }">
          <div v-if="row.ai_tags?.length" class="flex flex-wrap gap-1">
            <el-tag v-for="tag in row.ai_tags.slice(0, 4)" :key="tag" size="small" effect="plain">
              {{ tag }}
            </el-tag>
            <el-tag v-if="row.ai_tags.length > 4" size="small" effect="plain" type="info">
              +{{ row.ai_tags.length - 4 }}
            </el-tag>
          </div>
          <span v-else class="text-content-tertiary">-</span>
        </template>
      </el-table-column>

      <el-table-column label="创建时间" width="110">
        <template #default="{ row }">
          <div class="text-xs text-content-secondary">
            {{ row.created_at?.slice(0, 10) || '-' }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="80" fixed="right" align="center">
        <template #default="{ row }">
          <el-button
            type="primary"
            size="small"
            :icon="View"
            :disabled="row.status === 0 || row.status === 1 || row.status === 2"
            @click="handleView(row)"
            title="查看详情"
          />
        </template>
      </el-table-column>
    </el-table>

    <div class="mt-4 flex justify-end">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :pager-count="7"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <div v-if="!loading && digests.length === 0" class="mt-10 text-center">
      <el-empty description="暂无日报数据">
        <el-button type="primary" @click="handleTrigger">生成第一份日报</el-button>
      </el-empty>
    </div>
  </div>
</template>
