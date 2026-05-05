<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCollectTaskList, deleteCollectTask, retryCollectTask } from '@/api/collector'
import type { CollectTaskListDTO } from '@/types/collector'
import { CollectTaskStatusMap, CollectTaskTypeMap } from '@/types/collector'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Refresh, Search, View } from '@element-plus/icons-vue'
import TaskCreateDialog from '@/components/collector/TaskCreateDialog.vue'

const router = useRouter()
const loading = ref(false)
const tasks = ref<CollectTaskListDTO[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const searchKeyword = ref('')
const filterStatus = ref<number | undefined>(undefined)
const filterType = ref<string | undefined>(undefined)
const showCreateDialog = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res = await getCollectTaskList({
      current: currentPage.value,
      size: pageSize.value,
      status: filterStatus.value,
      taskType: filterType.value,
      keyword: searchKeyword.value || undefined,
    })
    tasks.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  currentPage.value = 1
  fetchData()
}

function clearSearch(): void {
  searchKeyword.value = ''
  filterStatus.value = undefined
  filterType.value = undefined
  handleSearch()
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchData()
}

function handleView(row: CollectTaskListDTO): void {
  router.push(`/admin/collector/${row.id}`)
}

async function handleRetry(row: CollectTaskListDTO): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要重试此任务吗？', '提示', { type: 'warning' })
    await retryCollectTask(row.id)
    ElMessage.success('任务已重新提交')
    fetchData()
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') return
  }
}

async function handleDelete(row: CollectTaskListDTO): Promise<void> {
  try {
    await ElMessageBox.confirm('确定要删除此任务吗？相关页面数据将一并删除。', '提示', { type: 'warning' })
    await deleteCollectTask(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') return
  }
}

function isTerminal(status: number): boolean {
  // PENDING(0)/COMPLETED(3)/FAILED(4) 均可删除；CRAWLING(1)/PROCESSING(2) 禁止删除
  return status === 0 || status === 3 || status === 4
}

function hasActiveTasks(): boolean {
  return tasks.value.some(t => t.status === 0 || t.status === 1 || t.status === 2)
}

function startPolling(): void {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (hasActiveTasks() && !loading.value) fetchData()
  }, 5000)
}

function stopPolling(): void {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  fetchData()
  startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-content-primary">内容采集</h2>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">
        新建采集
      </el-button>
    </div>

    <!-- Filter Bar -->
    <div class="mb-4 flex items-center gap-3">
      <div class="relative flex-1 max-w-md">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索 URL / 关键词..."
          clearable
          @keyup.enter="handleSearch"
          @clear="clearSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 130px" @change="handleSearch">
        <el-option
          v-for="(s, key) in CollectTaskStatusMap"
          :key="key"
          :label="s.label"
          :value="Number(key)"
        />
      </el-select>
      <el-select v-model="filterType" placeholder="类型" clearable style="width: 140px" @change="handleSearch">
        <el-option
          v-for="(t, key) in CollectTaskTypeMap"
          :key="key"
          :label="t.label"
          :value="key"
        />
      </el-select>
      <el-button type="primary" @click="handleSearch">搜索</el-button>
      <el-button v-if="searchKeyword || filterStatus || filterType" @click="clearSearch">重置</el-button>
    </div>

    <el-table v-loading="loading" :data="tasks" border>
      <el-table-column label="ID" prop="id" width="70" align="center" />

      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-tag :type="CollectTaskTypeMap[row.taskType]?.type || 'info'" size="small">
            {{ CollectTaskTypeMap[row.taskType]?.label || row.taskType }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="来源 / 关键词" min-width="220">
        <template #default="{ row }">
          <div v-if="row.sourceUrl" class="truncate text-sm" :title="row.sourceUrl">
            {{ row.sourceUrl }}
          </div>
          <div v-else-if="row.keyword" class="text-sm font-medium text-primary">
            {{ row.keyword }}
          </div>
          <div v-else class="text-content-tertiary">-</div>
          <div v-if="row.aiTitle" class="mt-1 truncate text-xs text-content-secondary" :title="row.aiTitle">
            AI: {{ row.aiTitle }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="进度" width="150">
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <el-progress
              :percentage="row.progressPercent"
              :stroke-width="8"
              :show-text="false"
              :color="row.status === 4 ? '#EF4444' : undefined"
              class="flex-1"
            />
            <span class="text-xs text-content-tertiary whitespace-nowrap">
              {{ row.completedPages }}/{{ row.totalPages }}
            </span>
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
              {{ CollectTaskStatusMap[row.status]?.label || '未知' }}
            </div>
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="字数" width="90" align="center">
        <template #default="{ row }">
          <span class="text-sm">{{ row.totalWordCount?.toLocaleString() || '-' }}</span>
        </template>
      </el-table-column>

      <el-table-column label="创建时间" width="110">
        <template #default="{ row }">
          <div class="text-xs text-content-secondary">
            {{ row.createdAt?.slice(0, 10) || '-' }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="160" fixed="right" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button type="primary" size="small" :icon="View" @click="handleView(row)" title="查看详情" />
            <el-button
              v-if="row.status === 4"
              type="warning"
              size="small"
              :icon="Refresh"
              @click="handleRetry(row)"
              title="重试"
            />
            <el-button
              v-if="isTerminal(row.status)"
              type="danger"
              size="small"
              :icon="Delete"
              @click="handleDelete(row)"
              title="删除"
            />
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <div class="mt-4 flex justify-end">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="handlePageChange"
      />
    </div>

    <!-- Create Dialog -->
    <TaskCreateDialog v-model:visible="showCreateDialog" @success="fetchData" />
  </div>
</template>
