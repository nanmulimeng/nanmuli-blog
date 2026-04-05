<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Edit, Delete, Share, Link } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminDailyLogList, deleteDailyLog } from '@/api/dailyLog'
import { formatDateCN } from '@/utils/format'
import type { DailyLog } from '@/types/dailyLog'

const router = useRouter()
const loading = ref(false)
const logs = ref<DailyLog[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

const moodMap: Record<string, { label: string; color: string }> = {
  happy: { label: '开心', color: '#f59e0b' },
  excited: { label: '兴奋', color: '#ef4444' },
  normal: { label: '平静', color: '#64748B' },
  tired: { label: '疲惫', color: '#3B82F6' },
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res = await getAdminDailyLogList({
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
  } catch (error: any) {
    // 用户取消对话框时会抛出 'cancel'，不需要提示
    if (error === 'cancel' || error?.message === 'cancel') {
      return
    }
    console.error('删除日志失败:', error)
  }
}

function handleShare(row: DailyLog): void {
  if (!row.isPublic) {
    ElMessage.warning('请先编辑日志设置为公开分享')
    return
  }
  const shareUrl = `${window.location.origin}/daily-log/${row.id}`
  navigator.clipboard.writeText(shareUrl).then(() => {
    ElMessage.success('分享链接已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制链接')
  })
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
      <h2 class="text-xl font-bold text-content-primary">日志管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建日志
      </el-button>
    </div>

    <el-table v-loading="loading" :data="logs" border>
      <el-table-column type="index" label="序号" width="60" />
      <el-table-column prop="logDate" label="日期" width="120">
        <template #default="{ row }">
          {{ formatDateCN(row.logDate) }}
        </template>
      </el-table-column>
      <el-table-column label="分类" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.category" size="small" :style="{ backgroundColor: row.category.color + '20', color: row.category.color, borderColor: row.category.color }"
            >{{ row.category.name }}</el-tag
          >
          <span v-else class="text-content-tertiary">-</span>
        </template>
      </el-table-column>

      <el-table-column label="内容预览" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="text-content-secondary">
            {{ row.content?.replace(/[#*`\[\]]/g, '').slice(0, 50) || '无内容' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="mood" label="心情" width="90">
        <template #default="{ row }">
          <span
            v-if="row.mood"
            class="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs"
            :style="{
              backgroundColor: moodMap[row.mood]?.color + '20' || '#64748B20',
              color: moodMap[row.mood]?.color || '#64748B'
            }"
          >
            {{ moodMap[row.mood]?.label || row.mood }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="weather" label="天气" width="90" />
      <el-table-column prop="wordCount" label="字数" width="80" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.isPublic" type="success" size="small">公开</el-tag>
          <el-tag v-else type="info" size="small">私有</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button
            type="success"
            link
            :icon="Share"
            :disabled="!row.isPublic"
            @click="handleShare(row)"
          >
            分享
          </el-button>
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

<style scoped>
/* 表格样式已由全局样式处理 */
</style>
