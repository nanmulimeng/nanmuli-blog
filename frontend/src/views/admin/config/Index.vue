<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminConfigList, updateConfig } from '@/api/config'
import { testAiConnection } from '@/api/ai'
import type { Config } from '@/types/config'

const loading = ref(false)
const aiTesting = ref(false)
const configs = ref<Config[]>([])
const formData = ref<Record<string, string | number>>({})
// AI 提供商预设
const aiProviders = [
  { label: 'DeepSeek', value: 'deepseek', defaultUrl: 'https://api.deepseek.com/v1', defaultModel: 'deepseek-chat' },
  { label: '阿里云 DashScope (Qwen)', value: 'dashscope', defaultUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', defaultModel: 'qwen-turbo' },
  { label: 'OpenAI', value: 'openai', defaultUrl: 'https://api.openai.com/v1', defaultModel: 'gpt-3.5-turbo' },
  { label: '自定义', value: 'custom', defaultUrl: '', defaultModel: '' },
]

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    configs.value = await getAdminConfigList()
    configs.value.forEach((config) => {
      const numKeys = ['ai.temperature', 'ai.connect_timeout_seconds', 'ai.read_timeout_seconds']
      if (numKeys.includes(config.configKey)) {
        const n = Number(config.configValue)
        formData.value[config.configKey] = isNaN(n) ? 0 : n
      } else {
        formData.value[config.configKey] = config.configValue
      }
    })
  } finally {
    loading.value = false
  }
}

async function handleSave(key: string): Promise<void> {
  try {
    const value = formData.value[key]
    if (value === undefined) return
    await updateConfig(key, String(value))
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败')
  }
}

async function handleSaveAiGroup(): Promise<void> {
  const aiKeys = configs.value
    .filter(c => c.groupName === 'ai')
    .map(c => c.configKey)

  try {
    for (const key of aiKeys) {
      const value = formData.value[key]
      if (value !== undefined) {
        await updateConfig(key, String(value))
      }
    }
    ElMessage.success('AI 配置保存成功')
  } catch {
    ElMessage.error('AI 配置保存失败')
  }
}

async function handleAiTest(): Promise<void> {
  aiTesting.value = true
  try {
    const result = await testAiConnection()
    if (result.available) {
      ElMessageBox.alert(
        `提供商：${result.provider || '未知'}\n模型：${result.model || '未知'}\n连接成功！`,
        'AI 连接测试',
        { type: 'success' }
      )
    } else {
      ElMessageBox.alert(
        result.reason || '连接失败',
        'AI 连接测试',
        { type: 'warning' }
      )
    }
  } catch (e: any) {
    ElMessage.error('测试失败：' + (e.message || '未知错误'))
  } finally {
    aiTesting.value = false
  }
}

function onProviderChange(provider: string): Promise<void> {
  const preset = aiProviders.find(p => p.value === provider)
  if (!preset) return Promise.resolve()

  // 自动填充默认值（仅当当前值为空或与旧默认值匹配时）
  const baseUrl = String(formData.value['ai.base_url'] || '')
  const modelVal = String(formData.value['ai.model'] || '')
  if (preset.defaultUrl && (!baseUrl || isDefaultUrl(baseUrl))) {
    formData.value['ai.base_url'] = preset.defaultUrl
  }
  if (preset.defaultModel && (!modelVal || isDefaultModel(modelVal))) {
    formData.value['ai.model'] = preset.defaultModel
  }
  return Promise.resolve()
}

function isDefaultUrl(url: string): boolean {
  return aiProviders.some(p => p.defaultUrl === url)
}

function isDefaultModel(model: string): boolean {
  return aiProviders.some(p => p.defaultModel === model)
}

const groupNames: Record<string, string> = {
  site: '站点配置',
  ai: 'AI 配置',
}

const groupedConfigs = computed(() => {
  const groups: Record<string, Config[]> = {}
  configs.value.forEach((config) => {
    const group = config.groupName || 'other'
    if (!groups[group]) {
      groups[group] = []
    }
    groups[group]!.push(config)
  })
  return groups
})

onMounted(fetchData)
</script>

<template>
  <div>
    <h2 class="mb-6 text-xl font-bold text-content-primary">系统配置</h2>

    <div v-for="(items, group) in groupedConfigs" :key="group" class="mb-8">
      <h3 class="mb-4 text-lg font-semibold text-content-secondary">
        {{ groupNames[group] || group }}
      </h3>

      <!-- AI 配置专用面板 -->
      <template v-if="group === 'ai'">
        <div class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <!-- 启用开关 -->
          <div class="mb-6 flex items-center justify-between">
            <div>
              <span class="font-medium text-content-primary">启用 AI 内容整理</span>
              <p class="mt-1 text-sm text-content-tertiary">
                开启后，爬虫任务爬取完成将自动调用 AI 进行内容整理
              </p>
            </div>
            <el-switch
              v-model="formData['ai.enabled']"
              active-value="true"
              inactive-value="false"
              @change="handleSave('ai.enabled')"
            />
          </div>

          <el-divider />

          <!-- 提供商选择 -->
          <div class="mb-4">
            <label class="mb-2 block text-sm font-medium text-content-primary">AI 提供商</label>
            <el-select
              v-model="formData['ai.provider']"
              style="width: 280px"
              @change="onProviderChange"
            >
              <el-option
                v-for="p in aiProviders"
                :key="p.value"
                :label="p.label"
                :value="p.value"
              />
            </el-select>
          </div>

          <!-- API 密钥 -->
          <div class="mb-4">
            <label class="mb-2 block text-sm font-medium text-content-primary">API 密钥</label>
            <div class="flex gap-3">
              <el-input
                v-model="formData['ai.api_key']"
                placeholder="输入 API 密钥"
                style="width: 400px"
                show-password
              />
            </div>
          </div>

          <!-- Base URL -->
          <div class="mb-4">
            <label class="mb-2 block text-sm font-medium text-content-primary">Base URL</label>
            <el-input
              v-model="formData['ai.base_url']"
              placeholder="https://api.example.com/v1"
              style="width: 480px"
            />
          </div>

          <!-- 模型名称 -->
          <div class="mb-4">
            <label class="mb-2 block text-sm font-medium text-content-primary">模型名称</label>
            <el-input
              v-model="formData['ai.model']"
              placeholder="deepseek-chat / qwen-turbo / gpt-3.5-turbo"
              style="width: 320px"
            />
          </div>

          <!-- 温度系数 -->
          <div class="mb-6">
            <label class="mb-2 block text-sm font-medium text-content-primary">
              温度系数: {{ formData['ai.temperature'] !== undefined ? formData['ai.temperature'] : '0.3' }}
            </label>
            <el-slider
              :model-value="Number(formData['ai.temperature'] ?? 0.3)"
              :min="0"
              :max="2"
              :step="0.1"
              style="width: 320px"
              @update:model-value="(v) => formData['ai.temperature'] = Number(v)"
            />
            <p class="mt-1 text-xs text-content-tertiary">
              越低越严谨（0），越高越创意（2）。建议技术文章使用 0.2-0.5
            </p>
          </div>

          <!-- 超时配置 -->
          <div class="mb-6 flex gap-6">
            <div>
              <label class="mb-1 block text-sm font-medium text-content-primary">连接超时（秒）</label>
              <el-input-number
                :model-value="Number(formData['ai.connect_timeout_seconds'] || 10)"
                :min="1"
                :max="60"
                @update:model-value="(v) => formData['ai.connect_timeout_seconds'] = Number(v)"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-content-primary">读取超时（秒）</label>
              <el-input-number
                :model-value="Number(formData['ai.read_timeout_seconds'] || 90)"
                :min="1"
                :max="300"
                @update:model-value="(v) => formData['ai.read_timeout_seconds'] = Number(v)"
              />
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex gap-4">
            <el-button type="primary" @click="handleSaveAiGroup">
              保存 AI 配置
            </el-button>
            <el-button :loading="aiTesting" @click="handleAiTest">
              测试连接
            </el-button>
          </div>
        </div>
      </template>

      <!-- 普通配置 -->
      <template v-else>
        <el-form label-width="120px">
          <el-form-item
            v-for="config in items"
            :key="config.configKey"
            :label="config.description || config.configKey"
          >
            <div class="flex gap-4">
              <el-input
                v-model="formData[config.configKey]"
                style="width: 400px"
              />
              <el-button type="primary" @click="handleSave(config.configKey)">
                保存
              </el-button>
            </div>
            <template v-if="config.defaultValue">
              <p class="mt-1 text-xs text-content-tertiary">
                默认值: {{ config.defaultValue }}
              </p>
            </template>
          </el-form-item>
        </el-form>
      </template>
    </div>
  </div>
</template>
