<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import { getAdminConfigList, updateConfig } from '@/api/config'
import type { Config } from '@/types/config'
import FileUpload from '@/components/common/FileUpload.vue'

const loading = ref(false)
const savingGroup = ref<string | null>(null)
const configs = ref<Config[]>([])
const formData = ref<Record<string, string>>({})

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    configs.value = await getAdminConfigList()
    configs.value.forEach((config) => {
      formData.value[config.configKey] = config.configValue ?? ''
    })
  } finally {
    loading.value = false
  }
}

async function handleSave(key: string): Promise<void> {
  const value = formData.value[key]
  if (value === undefined) return
  try {
    await updateConfig(key, value)
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败')
  }
}

async function handleSaveGroup(group: string): Promise<void> {
  const keys = configs.value
    .filter((c) => c.groupName === group)
    .map((c) => c.configKey)

  if (keys.length === 0) return

  savingGroup.value = group
  try {
    for (const key of keys) {
      const value = formData.value[key]
      if (value !== undefined) {
        await updateConfig(key, value)
      }
    }
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingGroup.value = null
  }
}

function handleReset(key: string, defaultValue?: string): void {
  if (defaultValue !== undefined) {
    formData.value[key] = defaultValue
  }
}

const groupNames: Record<string, string> = {
  site: '站点配置',
  ai: 'AI 配置',
  crawler: '爬虫配置',
}

const groupDescriptions: Record<string, string> = {
  site: '配置网站基本信息、联系方式与页面内容',
  ai: '控制 AI 辅助功能的开关与模型参数',
  crawler: '控制 Python 爬虫服务的 AI 整理、日报生成与代理设置',
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

// 配置项渲染类型判断
function getInputType(configKey: string): 'text' | 'textarea' | 'switch' | 'image' | 'password' {
  if (configKey.endsWith('.enabled') || configKey.endsWith('.autoTags') || configKey.endsWith('.autoSummary')) {
    return 'switch'
  }
  if (['site.logo', 'site.favicon', 'site.avatar'].includes(configKey)) {
    return 'image'
  }
  if (['site.about', 'site.footer', 'site.description'].includes(configKey)) {
    return 'textarea'
  }
  if (configKey.endsWith('.api_key') || configKey.endsWith('.secret')) {
    return 'password'
  }
  return 'text'
}

// 获取配置项的简短标签（去除前缀）
function getShortLabel(configKey: string): string {
  const parts = configKey.split('.')
  return parts.length > 1 ? parts.slice(1).join('.') : configKey
}

function handleImageChange(configKey: string, url: string): void {
  formData.value[configKey] = url
  handleSave(configKey)
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-content-primary">系统配置</h2>
        <p class="mt-1 text-sm text-content-tertiary">
          管理网站公开配置项，修改后前台页面将实时生效
        </p>
      </div>
      <el-button type="primary" :icon="RefreshRight" :loading="loading" @click="fetchData">
        刷新
      </el-button>
    </div>

    <div v-loading="loading" class="space-y-8">
      <div v-for="(items, group) in groupedConfigs" :key="group">
        <!-- Group Header -->
        <div class="mb-4 flex items-center justify-between">
          <div>
            <h3 class="text-lg font-semibold text-content-primary">
              {{ groupNames[group] || group }}
            </h3>
            <p class="mt-0.5 text-xs text-content-tertiary">
              {{ groupDescriptions[group] || '' }}
            </p>
          </div>
          <el-button
            type="primary"
            size="small"
            :loading="savingGroup === group"
            @click="handleSaveGroup(group)"
          >
            保存全部
          </el-button>
        </div>

        <!-- Config Card -->
        <div class="rounded-2xl border border-border bg-surface-secondary p-6 shadow-sm">
          <div class="space-y-6">
            <div
              v-for="config in items"
              :key="config.configKey"
              class="flex flex-col gap-3 sm:flex-row sm:items-start"
            >
              <!-- Label -->
              <div class="w-full sm:w-40 flex-shrink-0 pt-2">
                <label class="text-sm font-medium text-content-primary">
                  {{ config.description || getShortLabel(config.configKey) }}
                </label>
                <p class="mt-0.5 text-xs text-content-tertiary font-mono">
                  {{ config.configKey }}
                </p>
              </div>

              <!-- Input Area -->
              <div class="flex-1 min-w-0">
                <!-- Switch -->
                <template v-if="getInputType(config.configKey) === 'switch'">
                  <el-switch
                    v-model="formData[config.configKey]"
                    active-value="true"
                    inactive-value="false"
                    @change="handleSave(config.configKey)"
                  />
                  <span class="ml-3 text-sm text-content-secondary">
                    {{ formData[config.configKey] === 'true' ? '已启用' : '已禁用' }}
                  </span>
                </template>

                <!-- Image Upload -->
                <template v-else-if="getInputType(config.configKey) === 'image'">
                  <FileUpload
                    :model-value="formData[config.configKey] || ''"
                    placeholder="输入图片 URL 或点击上传"
                    @update:model-value="(url) => handleImageChange(config.configKey, url)"
                  />
                </template>

                <!-- Textarea -->
                <template v-else-if="getInputType(config.configKey) === 'textarea'">
                  <el-input
                    v-model="formData[config.configKey]"
                    type="textarea"
                    :rows="config.configKey === 'site.about' ? 6 : 3"
                    :placeholder="`输入${config.description || getShortLabel(config.configKey)}`"
                    @blur="handleSave(config.configKey)"
                  />
                </template>

                <!-- Password Input -->
                <template v-else-if="getInputType(config.configKey) === 'password'">
                  <el-input
                    v-model="formData[config.configKey]"
                    type="password"
                    show-password
                    :placeholder="`输入${config.description || getShortLabel(config.configKey)}`"
                    @blur="handleSave(config.configKey)"
                  />
                </template>

                <!-- Text Input -->
                <template v-else>
                  <el-input
                    v-model="formData[config.configKey]"
                    :placeholder="`输入${config.description || getShortLabel(config.configKey)}`"
                    clearable
                    @blur="handleSave(config.configKey)"
                  />
                </template>

                <!-- Default Value Hint -->
                <div v-if="config.defaultValue" class="mt-1.5 flex items-center gap-2">
                  <span class="text-xs text-content-tertiary">
                    默认值: {{ config.defaultValue }}
                  </span>
                  <el-button
                    v-if="formData[config.configKey] !== config.defaultValue"
                    link
                    type="primary"
                    size="small"
                    class="text-xs"
                    @click="handleReset(config.configKey, config.defaultValue)"
                  >
                    恢复默认
                  </el-button>
                </div>

                <!-- Sensitive Warning -->
                <div v-if="config.sensitive" class="mt-1.5">
                  <el-tag type="warning" size="small" effect="plain">
                    敏感配置 - 公开接口将脱敏显示
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty State -->
      <div v-if="!loading && configs.length === 0" class="py-20 text-center">
        <el-empty description="暂无配置数据" />
      </div>
    </div>
  </div>
</template>
