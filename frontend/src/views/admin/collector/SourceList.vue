<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getSourceList, createSource, updateSource, deleteSource, toggleSource } from '@/api/collector'
import type { Source, CreateSourceCommand } from '@/types/collector'
import { SourceTypeMap, ContentCategoryMap } from '@/types/collector'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, Edit } from '@element-plus/icons-vue'

const loading = ref(false)
const sources = ref<Source[]>([])
const showDialog = ref(false)
const editingId = ref<string | null>(null)

const form = ref<CreateSourceCommand & { isActive?: boolean }>({
  name: '',
  type: 'keyword',
  value: '',
  contentCategory: undefined,
  crawlMode: 'single',
  maxDepth: 1,
  maxPages: 10,
  aiTemplate: 'tech_summary',
  freshnessHours: 24,
})

const categoryOptions = Object.entries(ContentCategoryMap).map(([key, val]) => ({
  value: key,
  label: val.label,
}))

const typeOptions = [
  { value: 'keyword', label: '关键词' },
  { value: 'url', label: 'URL' },
  { value: 'rss', label: 'RSS' },
]

const templateOptions = [
  { value: 'tech_summary', label: '技术文档摘要' },
  { value: 'tutorial', label: '教程提炼' },
  { value: 'comparison', label: '对比分析' },
  { value: 'knowledge_report', label: '知识报告' },
]

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    sources.value = await getSourceList()
  } finally {
    loading.value = false
  }
}

function openCreate(): void {
  editingId.value = null
  form.value = {
    name: '', type: 'keyword', value: '', contentCategory: undefined,
    crawlMode: 'single', maxDepth: 1, maxPages: 10,
    aiTemplate: 'tech_summary', freshnessHours: 24,
  }
  showDialog.value = true
}

function openEdit(row: Source): void {
  editingId.value = row.id
  form.value = {
    name: row.name, type: row.type, value: row.value,
    contentCategory: row.contentCategory || undefined,
    crawlMode: row.crawlMode || 'single',
    maxDepth: row.maxDepth || 1, maxPages: row.maxPages || 10,
    aiTemplate: row.aiTemplate || 'tech_summary',
    freshnessHours: row.freshnessHours || 24,
    isActive: row.isActive,
  }
  showDialog.value = true
}

async function handleSubmit(): Promise<void> {
  if (!form.value.name || !form.value.value) {
    ElMessage.warning('名称和值不能为空')
    return
  }
  try {
    if (editingId.value) {
      await updateSource(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createSource(form.value)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    fetchData()
  } catch { /* request util handles error */ }
}

async function handleDelete(row: Source): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除订阅源「${row.name}」吗？`, '提示', { type: 'warning' })
    await deleteSource(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error: unknown) {
    if (error === 'cancel' || (error instanceof Error && error.message === 'cancel')) return
  }
}

async function handleToggle(row: Source): Promise<void> {
  try {
    await toggleSource(row.id)
    fetchData()
  } catch { /* request util handles error */ }
}

function categoryLabel(cat: string | null): string {
  if (!cat) return '-'
  return ContentCategoryMap[cat]?.label || cat
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-content-primary">订阅源管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增订阅源</el-button>
    </div>

    <el-table v-loading="loading" :data="sources" border>
      <el-table-column label="名称" min-width="160">
        <template #default="{ row }">
          <div class="font-medium text-content-primary">{{ row.name }}</div>
          <div class="mt-1 truncate text-xs text-content-tertiary" :title="row.value">
            {{ row.value }}
          </div>
        </template>
      </el-table-column>

      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="SourceTypeMap[row.type]?.type || 'info'" size="small">
            {{ SourceTypeMap[row.type]?.label || row.type }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="内容分类" width="120">
        <template #default="{ row }">
          <span v-if="row.contentCategory" class="text-sm">
            <span
              class="mr-1 inline-block h-2 w-2 rounded-full"
              :style="{ backgroundColor: ContentCategoryMap[row.contentCategory]?.color || '#6b7280' }"
            />
            {{ categoryLabel(row.contentCategory) }}
          </span>
          <span v-else class="text-content-tertiary">-</span>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.isActive"
            size="small"
            @change="handleToggle(row)"
          />
        </template>
      </el-table-column>

      <el-table-column label="运行次数" width="90" align="center">
        <template #default="{ row }">
          <span class="text-sm">{{ row.runCount || 0 }}</span>
        </template>
      </el-table-column>

      <el-table-column label="上次运行" width="110">
        <template #default="{ row }">
          <div v-if="row.lastRunAt" class="text-xs text-content-secondary">
            {{ row.lastRunAt.slice(0, 10) }}
          </div>
          <div v-else class="text-content-tertiary">-</div>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="140" fixed="right" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button type="primary" size="small" :icon="Edit" @click="openEdit(row)" title="编辑" />
            <el-button type="danger" size="small" :icon="Delete" @click="handleDelete(row)" title="删除" />
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="!loading && sources.length === 0" class="mt-10 text-center">
      <el-empty description="暂无订阅源" />
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="showDialog"
      :title="editingId ? '编辑订阅源' : '新增订阅源'"
      width="560px"
      destroy-on-close
    >
      <el-form label-width="100px" label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：GitHub Trending" maxlength="200" />
        </el-form-item>

        <div class="grid grid-cols-2 gap-4">
          <el-form-item label="类型" required>
            <el-select v-model="form.type" class="w-full">
              <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="内容分类">
            <el-select v-model="form.contentCategory" clearable placeholder="选择分类" class="w-full">
              <el-option v-for="c in categoryOptions" :key="c.value" :label="c.label" :value="c.value" />
            </el-select>
          </el-form-item>
        </div>

        <el-form-item :label="form.type === 'keyword' ? '关键词' : form.type === 'url' ? 'URL' : 'RSS 地址'" required>
          <el-input v-model="form.value" :placeholder="form.type === 'keyword' ? '如：GitHub trending' : 'https://...'" maxlength="2048" />
        </el-form-item>

        <div class="grid grid-cols-3 gap-4">
          <el-form-item label="AI 模板">
            <el-select v-model="form.aiTemplate" class="w-full">
              <el-option v-for="t in templateOptions" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="最大深度">
            <el-input-number v-model="form.maxDepth" :min="1" :max="3" class="w-full" />
          </el-form-item>
          <el-form-item label="最大页数">
            <el-input-number v-model="form.maxPages" :min="1" :max="20" class="w-full" />
          </el-form-item>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <el-form-item label="内容新鲜度(小时)">
            <el-input-number v-model="form.freshnessHours" :min="1" :max="720" class="w-full" />
          </el-form-item>
          <el-form-item v-if="editingId" label="启用状态">
            <el-switch v-model="form.isActive" />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">{{ editingId ? '更新' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
