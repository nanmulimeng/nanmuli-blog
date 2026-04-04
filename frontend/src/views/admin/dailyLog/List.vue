<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDailyLogList, deleteDailyLog } from '@/api/dailyLog'
import { formatDate } from '@/utils/format'
import type { DailyLog } from '@/types/dailyLog'

const router = useRouter()
const loading = ref(false)
const logs = ref<DailyLog[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const moodMap: Record<string, string> = {
  happy: '😊 开心',
  excited: '🤩 兴奋',
  normal: '😐 平静',
  tired: '😴 疲惫',
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res = await getDailyLogList({
      current: currentPage.value,
      size: pageSize.value,
    })
    logs.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleCreate(): void {
  router.push('/admin/daily-log/create')
}

function handleEdit(row: DailyLog): void {
  router.push(`/admin/daily-log/edit/${row.id}`)
}

async function handleDelete(row: DailyLog): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除这条日志吗？`, '提示', {
      type: 'warning',
    })
    await deleteDailyLog(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消
  }
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchData()
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-gray-900">日志管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建日志
      </el-button>
    </div>

    <el-table v-loading="loading" :data="logs" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="logDate" label="日期" width="120">
        <template #default="{ row }">
          {{ formatDate(row.logDate) }}
        </template>
      </el-table-column>
      <el-table-column prop="mood" label="心情" width="100">
        <template #default="{ row }">
          {{ moodMap[row.mood] || row.mood }}
        </template>
      </el-table-column>
      <el-table-column prop="weather" label="天气" width="100" />
      <el-table-column prop="wordCount" label="字数" width="100" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">
            编辑
          </el-button>
          <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">
            删除
          </el-button>
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
  </div>
</template>
