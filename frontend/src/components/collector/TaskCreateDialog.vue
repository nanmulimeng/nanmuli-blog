<script setup lang="ts">
import { ref, computed } from 'vue'
import { createCollectTask } from '@/api/collector'
import { AiTemplateMap } from '@/types/collector'
import type { CreateCollectTaskCommand } from '@/types/collector'
import { ElMessage } from 'element-plus'

const emit = defineEmits<{
  (e: 'success'): void
}>()

const visible = defineModel<boolean>('visible', { default: false })
const loading = ref(false)

const form = ref<CreateCollectTaskCommand>({
  taskType: 'single',
  maxDepth: 1,
  maxPages: 10,
  searchEngine: 'sogou',
  aiTemplate: 'tech_summary',
})

const taskTypes = [
  { value: 'single', label: '单页爬取', desc: '爬取单个网页的内容' },
  { value: 'deep', label: '深度爬取', desc: 'BFS 深度爬取同域链接' },
  { value: 'keyword', label: '关键词搜索', desc: '通过搜索引擎搜索并爬取结果' },
]

const needUrl = computed(() => form.value.taskType === 'single' || form.value.taskType === 'deep')
const needKeyword = computed(() => form.value.taskType === 'keyword')
const needDepth = computed(() => form.value.taskType === 'deep')

const rules = computed(() => ({
  taskType: [{ required: true, message: '请选择任务类型', trigger: 'change' }],
  sourceUrl: needUrl.value ? [{ required: true, message: '请输入目标 URL', trigger: 'blur' }] : [],
  keyword: needKeyword.value ? [{ required: true, message: '请输入关键词', trigger: 'blur' }] : [],
}))

const formRef = ref()

function resetForm(): void {
  form.value = {
    taskType: 'single',
    maxDepth: 1,
    maxPages: 10,
    searchEngine: 'sogou',
    aiTemplate: 'tech_summary',
  }
}

async function handleSubmit(): Promise<void> {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    const payload: CreateCollectTaskCommand = { ...form.value }
    if (!needUrl.value) delete payload.sourceUrl
    if (!needKeyword.value) delete payload.keyword
    if (!needDepth.value) {
      delete payload.maxDepth
    }

    await createCollectTask(payload)
    ElMessage.success('任务已创建，正在后台执行')
    visible.value = false
    resetForm()
    emit('success')
  } finally {
    loading.value = false
  }
}

function handleClose(): void {
  resetForm()
  formRef.value?.resetFields()
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="新建采集任务"
    width="600px"
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="任务类型" prop="taskType">
        <el-radio-group v-model="form.taskType" class="flex flex-wrap gap-3">
          <el-radio
            v-for="t in taskTypes"
            :key="t.value"
            :value="t.value"
            class="!mr-0"
          >
            <div>
              <div class="font-medium">{{ t.label }}</div>
              <div class="text-xs text-content-tertiary">{{ t.desc }}</div>
            </div>
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="needUrl" label="目标 URL" prop="sourceUrl">
        <el-input
          v-model="form.sourceUrl"
          placeholder="https://example.com/article"
          clearable
        />
      </el-form-item>

      <el-form-item v-if="needKeyword" label="搜索关键词" prop="keyword">
        <el-input
          v-model="form.keyword"
          placeholder="输入关键词搜索..."
          clearable
          maxlength="500"
          show-word-limit
        />
      </el-form-item>

      <div v-if="needKeyword" class="mb-4">
        <el-form-item label="搜索引擎">
          <el-select v-model="form.searchEngine" class="w-full">
            <el-option label="搜狗 (推荐)" value="sogou" />
            <el-option label="Bing" value="bing" />
            <el-option label="DuckDuckGo" value="duckduckgo" />
            <el-option label="Google" value="google" />
          </el-select>
        </el-form-item>
      </div>

      <div v-if="needDepth || needKeyword" class="mb-4 flex gap-4">
        <el-form-item v-if="needDepth" label="最大深度" class="flex-1">
          <el-input-number v-model="form.maxDepth" :min="1" :max="3" class="w-full" />
        </el-form-item>
        <el-form-item v-if="needDepth || needKeyword" label="最大页数" class="flex-1">
          <el-input-number v-model="form.maxPages" :min="1" :max="20" class="w-full" />
        </el-form-item>
      </div>

      <el-form-item label="AI 整理模板">
        <el-select v-model="form.aiTemplate" class="w-full">
          <el-option
            v-for="(label, key) in AiTemplateMap"
            :key="key"
            :label="label"
            :value="key"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        开始采集
      </el-button>
    </template>
  </el-dialog>
</template>
