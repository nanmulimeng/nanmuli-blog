<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, FolderOpened, Search, CopyDocument, Delete } from '@element-plus/icons-vue'
import { getFileList, deleteFile } from '@/api/file'
import type { FileDTO, FilePageParams } from '@/api/file'
import SrcImage from '@/components/common/SrcImage.vue'

const loading = ref(false)
const files = ref<FileDTO[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(12)
const searchKeyword = ref('')
const fileTypeFilter = ref('')

const mimeTypeSimplified = computed(() => (mime: string): string => {
  if (mime.startsWith('image/')) return mime.replace('image/', '').toUpperCase()
  if (mime.startsWith('application/')) return mime.replace('application/', '').toUpperCase()
  if (mime.startsWith('text/')) return mime.replace('text/', '').toUpperCase()
  return mime || '-'
})

function formatFileSize(bytes: number): string {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

function formatDimensions(file: FileDTO): string {
  if (file.width && file.height) return `${file.width}×${file.height}`
  return '-'
}

function isImage(mimeType: string): boolean {
  return mimeType?.startsWith('image/')
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    const params: FilePageParams = {
      current: currentPage.value,
      size: pageSize.value,
      keyword: searchKeyword.value || undefined,
      fileType: fileTypeFilter.value || undefined,
    }
    const res = await getFileList(params)
    files.value = res.records
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  currentPage.value = 1
  fetchData()
}

function handleFilterChange(): void {
  currentPage.value = 1
  fetchData()
}

function handlePageChange(page: number): void {
  currentPage.value = page
  fetchData()
}

async function handleCopyLink(file: FileDTO): Promise<void> {
  await navigator.clipboard.writeText(file.fileUrl)
  ElMessage.success('链接已复制')
}

async function handleDelete(file: FileDTO): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定要删除 "${file.originalName}" 吗？文件链接将失效。`,
      '确认删除',
      { type: 'warning' }
    )
    await deleteFile(file.id)
    ElMessage.success('删除成功')
    if (files.value.length === 1 && currentPage.value > 1) {
      currentPage.value--
    }
    fetchData()
  } catch {
    // 用户取消
  }
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 class="text-xl font-bold text-content-primary">文件管理</h2>
      <p class="mt-1 text-sm text-content-tertiary">
        管理已上传的文件，支持搜索和筛选
      </p>
    </div>

    <!-- Search and Filter -->
    <div class="mb-4 flex items-center gap-3 flex-wrap">
      <div class="flex-1 min-w-[200px] max-w-md">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索文件名..."
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <el-select
        v-model="fileTypeFilter"
        placeholder="全部类型"
        clearable
        style="width: 140px"
        @change="handleFilterChange"
      >
        <el-option label="全部" value="" />
        <el-option label="图片" value="image" />
        <el-option label="文档" value="document" />
        <el-option label="其他" value="other" />
      </el-select>
      <el-button type="primary" @click="handleSearch">搜索</el-button>
    </div>

    <!-- File Table -->
    <el-table v-loading="loading" :data="files" border>
      <!-- Thumbnail -->
      <el-table-column label="缩略图" width="80" align="center">
        <template #default="{ row }">
          <div
            v-if="isImage(row.mimeType) && (row.thumbnailUrl || row.fileUrl)"
            class="h-12 w-12 mx-auto overflow-hidden rounded-lg border border-border bg-surface-tertiary"
          >
            <SrcImage
              :src="row.thumbnailUrl || row.fileUrl"
              :alt="row.originalName"
              :width="48"
              :height="48"
              :lazy="false"
            />
          </div>
          <div v-else class="flex h-12 w-12 mx-auto items-center justify-center rounded-lg bg-surface-tertiary">
            <el-icon :size="20" class="text-content-tertiary">
              <Document />
            </el-icon>
          </div>
        </template>
      </el-table-column>

      <!-- File Name -->
      <el-table-column prop="originalName" label="文件名" min-width="200">
        <template #default="{ row }">
          <span
            class="cursor-pointer text-content-primary hover:text-primary transition-colors"
            title="点击复制链接"
            @click="handleCopyLink(row)"
          >
            {{ row.originalName }}
          </span>
        </template>
      </el-table-column>

      <!-- Type -->
      <el-table-column label="类型" width="80" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ mimeTypeSimplified(row.mimeType) }}</el-tag>
        </template>
      </el-table-column>

      <!-- Size -->
      <el-table-column label="大小" width="90" align="center">
        <template #default="{ row }">
          <span class="text-sm text-content-secondary">{{ formatFileSize(row.fileSize) }}</span>
        </template>
      </el-table-column>

      <!-- Dimensions -->
      <el-table-column label="尺寸" width="110" align="center">
        <template #default="{ row }">
          <span class="text-sm text-content-secondary">{{ formatDimensions(row) }}</span>
        </template>
      </el-table-column>

      <!-- Create Time -->
      <el-table-column label="上传时间" width="160" align="center">
        <template #default="{ row }">
          <span class="text-sm text-content-secondary">{{ row.createTime?.slice(0, 16).replace('T', ' ') }}</span>
        </template>
      </el-table-column>

      <!-- Actions -->
      <el-table-column label="操作" width="110" fixed="right" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button size="small" :icon="CopyDocument" title="复制链接" @click="handleCopyLink(row)" />
            <el-button size="small" :icon="Delete" type="danger" title="删除" @click="handleDelete(row)" />
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <!-- Pagination -->
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

    <!-- Empty State -->
    <div v-if="!loading && files.length === 0" class="py-20 text-center">
      <el-empty :description="searchKeyword || fileTypeFilter ? '未找到匹配的文件' : '暂无上传文件'">
        <template v-if="!searchKeyword && !fileTypeFilter" #image>
          <el-icon :size="64" class="text-content-tertiary"><FolderOpened /></el-icon>
        </template>
      </el-empty>
    </div>
  </div>
</template>
