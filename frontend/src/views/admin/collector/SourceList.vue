<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getSourceList, createSource, updateSource, deleteSource, toggleSource, testSource } from '@/api/collector'
import type { Source, SourceTestResult, CreateSourceCommand } from '@/types/collector'
import { SourceTypeMap, ContentCategoryMap, AiTemplateMap } from '@/types/collector'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Plus, Delete, Edit, VideoPlay } from '@element-plus/icons-vue'

const loading = ref(false)
const sources = ref<Source[]>([])
const showDialog = ref(false)
const editingId = ref<string | null>(null)
const formRef = ref<FormInstance>()
const testingId = ref<string | null>(null)
const testDialogVisible = ref(false)
const testResult = ref<SourceTestResult | null>(null)

const form = ref<CreateSourceCommand & { isActive?: boolean }>({
  name: '',
  type: 'keyword',
  value: '',
  contentCategory: undefined,
  crawlMode: 'single',
  maxDepth: 1,
  maxPages: 10,
  cssSelector: '',
  aiTemplate: 'tech_summary',
  scheduleCron: '',
  freshnessHours: 24,
})

const formRules = computed<FormRules>(() => ({
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  value: [{ required: true, message: () => valueLabel.value + '不能为空', trigger: 'blur' }],
}))

const valueLabel = computed(() =>
  form.value.type === 'keyword' ? '关键词' : form.value.type === 'url' ? 'URL' : 'RSS 地址',
)

const categoryOptions = Object.entries(ContentCategoryMap).map(([key, val]) => ({
  value: key,
  label: val.label,
}))

const typeOptions = [
  { value: 'keyword', label: '关键词' },
  { value: 'url', label: 'URL' },
  { value: 'rss', label: 'RSS' },
]

const templateOptions = computed(() =>
  Object.entries(AiTemplateMap).map(([value, label]) => ({ value, label })),
)

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
    cssSelector: '', aiTemplate: 'tech_summary', scheduleCron: '',
    freshnessHours: 24,
  }
  showDialog.value = true
  formRef.value?.clearValidate()
}

function openEdit(row: Source): void {
  editingId.value = row.id
  form.value = {
    name: row.name, type: row.type, value: row.value,
    contentCategory: row.contentCategory || undefined,
    crawlMode: row.crawlMode || 'single',
    maxDepth: row.maxDepth || 1, maxPages: row.maxPages || 10,
    cssSelector: row.cssSelector || '',
    aiTemplate: row.aiTemplate || 'tech_summary',
    scheduleCron: row.scheduleCron || '',
    freshnessHours: row.freshnessHours || 24,
    isActive: row.isActive,
  }
  showDialog.value = true
  formRef.value?.clearValidate()
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
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

async function handleTest(row: Source): Promise<void> {
  testingId.value = row.id
  testResult.value = null
  try {
    const result = await testSource(row.id)
    testResult.value = result
    testDialogVisible.value = true
    if (result.crawlable) {
      ElMessage.success(`测试成功，抓取 ${result.success_count} 条有效内容`)
    } else {
      ElMessage.warning('测试完成，但没有抓取到有效内容')
    }
  } catch { /* request util handles error */ }
  finally {
    testingId.value = null
  }
}

function categoryLabel(cat: string | null): string {
  if (!cat) return '-'
  return ContentCategoryMap[cat]?.label || cat
}

function sourceRecommendation(row: Source): { label: string; type: 'success' | 'warning' | 'danger' | 'info'; hint: string } {
  const runCount = row.runCount || 0
  const failCount = row.failCount || 0
  const avgQuality = row.avgQualityScore
  const failRate = runCount > 0 ? failCount / runCount : 0

  if (!row.isActive) {
    return { label: '已停用', type: 'info', hint: '当前不会参与日报采集' }
  }
  if ((avgQuality != null && avgQuality < 40) || (runCount >= 3 && failRate >= 0.7) || (row.lastRunStatus === 'failed' && row.lastResultCount === 0)) {
    return { label: '建议停用', type: 'danger', hint: '连续失败或质量偏低，建议人工检查后再启用' }
  }
  if ((avgQuality != null && avgQuality < 60) || (runCount >= 3 && failRate >= 0.4) || row.lastError) {
    return { label: '建议复核', type: 'warning', hint: '来源稳定性或内容质量需要观察' }
  }
  if (runCount === 0) {
    return { label: '待验证', type: 'info', hint: '尚无运行数据，建议先测试一次' }
  }
  return { label: '继续使用', type: 'success', hint: '当前来源表现可继续使用' }
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

      <el-table-column label="运行统计" width="130">
        <template #default="{ row }">
          <div v-if="row.runCount" class="text-xs leading-relaxed">
            <div class="text-content-secondary">
              {{ row.runCount }} 次
              <template v-if="row.successCount != null || row.failCount != null">
                (<span class="text-success/70">{{ row.successCount || 0 }}成功</span>
                / <span class="text-error/70">{{ row.failCount || 0 }}失败</span>)
              </template>
            </div>
            <div v-if="row.avgQualityScore != null" class="text-content-tertiary">
              质量: {{ row.avgQualityScore.toFixed(1) }}
            </div>
            <div v-if="row.lastError" class="truncate text-error/60" :title="row.lastError">
              {{ row.lastError }}
            </div>
          </div>
          <span v-else class="text-content-tertiary">-</span>
        </template>
      </el-table-column>

      <el-table-column label="质量建议" width="120">
        <template #default="{ row }">
          <el-tag
            :type="sourceRecommendation(row).type"
            size="small"
            effect="plain"
            :title="sourceRecommendation(row).hint"
          >
            {{ sourceRecommendation(row).label }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="上次运行" width="110">
        <template #default="{ row }">
          <div v-if="row.lastRunAt" class="text-xs">
            <div class="text-content-secondary">{{ row.lastRunAt.slice(0, 10) }}</div>
            <el-tag
              v-if="row.lastRunStatus"
              :type="row.lastRunStatus === 'success' ? 'success' : 'danger'"
              size="small"
              class="mt-0.5"
            >
              {{ row.lastRunStatus === 'success' ? '成功' : '失败' }}
            </el-tag>
          </div>
          <div v-else class="text-content-tertiary">-</div>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="180" fixed="right" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button
              type="success"
              size="small"
              :icon="VideoPlay"
              :loading="testingId === row.id"
              @click="handleTest(row)"
              title="测试"
            />
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
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px" label-position="top">
        <el-form-item label="名称" prop="name">
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

        <el-form-item :label="valueLabel" prop="value">
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

        <div class="grid grid-cols-2 gap-4">
          <el-form-item label="CSS 选择器">
            <el-input v-model="form.cssSelector" placeholder="留空则自动提取正文" />
          </el-form-item>
          <el-form-item label="定时计划 (Cron)">
            <el-input v-model="form.scheduleCron" placeholder="留空则不自动执行" />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">{{ editingId ? '更新' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="testDialogVisible"
      title="订阅源测试结果"
      width="720px"
      destroy-on-close
    >
      <div v-if="testResult" class="space-y-4">
        <div class="grid grid-cols-3 gap-3 text-sm">
          <div>
            <div class="text-content-tertiary">有效内容</div>
            <div class="mt-1 text-lg font-semibold text-success">{{ testResult.success_count }}</div>
          </div>
          <div>
            <div class="text-content-tertiary">失败内容</div>
            <div class="mt-1 text-lg font-semibold text-error">{{ testResult.failed_count }}</div>
          </div>
          <div>
            <div class="text-content-tertiary">总计</div>
            <div class="mt-1 text-lg font-semibold text-content-primary">{{ testResult.total }}</div>
          </div>
        </div>

        <el-alert
          :type="testResult.crawlable ? 'success' : 'warning'"
          :closable="false"
          :title="testResult.crawlable ? '该订阅源可以被爬虫扫描' : '该订阅源暂未抓取到有效内容'"
        />

        <el-table :data="testResult.items" border size="small">
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.success ? 'success' : 'danger'" size="small">
                {{ row.success ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="180">
            <template #default="{ row }">
              <div class="truncate" :title="row.title || row.url">{{ row.title || row.url || '-' }}</div>
              <div v-if="row.url" class="mt-1 truncate text-xs text-content-tertiary" :title="row.url">{{ row.url }}</div>
            </template>
          </el-table-column>
          <el-table-column label="字数" width="80" prop="word_count" />
          <el-table-column label="错误" min-width="160">
            <template #default="{ row }">
              <span class="text-xs text-error/70">{{ row.error || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>
