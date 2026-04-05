<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getAdminArticleList, deleteArticle } from '@/api/article'
import { formatDate } from '@/utils/format'
import { ArticleStatusMap } from '@/constants'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import type { Article } from '@/types/article'

const router = useRouter()
const loading = ref(false)
const articles = ref<Article[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const res = await getAdminArticleList({
      current: currentPage.value,
      size: pageSize.value,
    })
    articles.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleCreate(): void {
  router.push('/admin/article/create')
}

function handleEdit(row: Article): void {
  router.push(`/admin/article/edit/${row.id}`)
}

async function handleDelete(row: Article): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除文章 "${row.title}" 吗？`, '提示', {
      type: 'warning',
    })
    await deleteArticle(row.id)
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
      <h2 class="text-xl font-bold text-gray-900">文章管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建文章
      </el-button>
    </div>

    <el-table v-loading="loading" :data="articles" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column label="分类" width="120">
        <template #default="{ row }">
          {{ row.category?.name }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="ArticleStatusMap[row.status]?.type || 'info'" size="small">
            {{ ArticleStatusMap[row.status]?.label || '未知' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="viewCount" label="阅读量" width="100" />
      <el-table-column label="发布时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.publishTime) }}
        </template>
      </el-table-column>
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
