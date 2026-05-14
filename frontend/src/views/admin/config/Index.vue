<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import { getAdminConfigList, updateConfig, getProxyStatus } from '@/api/config'
import type { Config, ProxyStatus } from '@/types/config'
import FileUpload from '@/components/common/FileUpload.vue'

const loading = ref(false)
const savingGroup = ref<string | null>(null)
const configs = ref<Config[]>([])
const formData = ref<Record<string, string>>({})

// 代理状态概览
const proxyStatus = ref<ProxyStatus | null>(null)

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    configs.value = await getAdminConfigList()
    configs.value.forEach((config) => {
      formData.value[config.configKey] = config.configValue ?? ''
    })
    await fetchProxyStatus()
  } finally {
    loading.value = false
  }
}

async function fetchProxyStatus(): Promise<void> {
  try {
    proxyStatus.value = await getProxyStatus()
  } catch {
    proxyStatus.value = null
  }
}

async function handleSave(key: string): Promise<void> {
  const value = formData.value[key]
  if (value === undefined) return
  try {
    await updateConfig(key, value)
    ElMessage.success('保存成功')
    // 保存代理相关配置后刷新代理状态
    if (key === 'crawler.proxy.enabled' || key === 'crawler.proxy.url') {
      await fetchProxyStatus()
    }
  } catch {
    ElMessage.error('保存失败')
  }
}

async function handleSaveGroup(group: string): Promise<void> {
  const items = groupedConfigs.value[group] || []
  if (items.length === 0) return

  savingGroup.value = group
  try {
    for (const config of items) {
      const value = formData.value[config.configKey]
      if (config.sensitive && value === '********') {
        continue
      }
      if (value !== undefined) {
        await updateConfig(config.configKey, value)
      }
    }
    ElMessage.success('保存成功')
    if (group === 'crawler-proxy' || group === 'crawler-ai') {
      await fetchProxyStatus()
    }
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingGroup.value = null
  }
}

const groupNames: Record<string, string> = {
  site: '站点配置',
  'crawler-ai': '爬虫AI配置',
  'crawler-proxy': '代理配置',
}

const groupDescriptions: Record<string, string> = {
  site: '配置网站基本信息、联系方式与页面内容',
  'crawler-ai': 'AI 内容整理与定时日报 — 模型参数、Token预算、字符限制',
  'crawler-proxy': 'HTTP 代理网络 — 代理地址、订阅链接、开关控制',
}

const groupOrder = ['crawler-ai', 'crawler-proxy', 'site']

const groupedConfigs = computed(() => {
  const groups: Record<string, Config[]> = {}
  configs.value.forEach((config) => {
    let group = config.groupName || 'other'
    // 将 crawler 组按前缀拆分为 AI 配置 / 代理配置两个 Tab
    if (group === 'crawler') {
      group = config.configKey.startsWith('crawler.proxy.') ? 'crawler-proxy' : 'crawler-ai'
    }
    if (!groups[group]) {
      groups[group] = []
    }
    groups[group]!.push(config)
  })
  return groups
})

function getInputType(config: { inputType?: string; configKey: string }): 'text' | 'textarea' | 'switch' | 'image' | 'password' {
  const type = config.inputType || 'text'
  if (['text', 'textarea', 'switch', 'image', 'password'].includes(type)) {
    return type as 'text' | 'textarea' | 'switch' | 'image' | 'password'
  }
  return 'text'
}

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
      <template v-for="group in groupOrder" :key="group">
        <div v-if="groupedConfigs[group]">
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
              v-for="config in groupedConfigs[group]"
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
                <template v-if="getInputType(config) === 'switch'">
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
                <template v-else-if="getInputType(config) === 'image'">
                  <FileUpload
                    :model-value="formData[config.configKey] || ''"
                    placeholder="输入图片 URL 或点击上传"
                    @update:model-value="(url) => handleImageChange(config.configKey, url)"
                  />
                </template>

                <!-- Textarea -->
                <template v-else-if="getInputType(config) === 'textarea'">
                  <el-input
                    v-model="formData[config.configKey]"
                    type="textarea"
                    :rows="config.configKey === 'site.about' ? 6 : 3"
                    :placeholder="`输入${config.description || getShortLabel(config.configKey)}`"
                    @blur="handleSave(config.configKey)"
                  />
                </template>

                <!-- Password Input -->
                <template v-else-if="getInputType(config) === 'password'">
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

        <!-- 代理概览卡片（仅代理配置组） -->
        <div v-if="group === 'crawler-proxy'" class="mt-4 rounded-2xl border border-border bg-surface-secondary p-5 shadow-sm">
          <div class="flex items-center justify-between mb-3">
            <h4 class="text-sm font-semibold text-content-primary">代理状态</h4>
            <router-link to="/admin/proxy" class="text-xs text-primary hover:underline">
              前往代理管理 →
            </router-link>
          </div>

          <div v-if="proxyStatus" class="grid grid-cols-3 gap-4">
            <div class="flex flex-col gap-1">
              <span class="text-xs text-content-tertiary">启用</span>
              <span class="text-sm font-medium" :class="proxyStatus.enabled ? 'text-green-600' : 'text-content-tertiary'">
                {{ proxyStatus.enabled ? '已启用' : '未启用' }}
              </span>
            </div>
            <div class="flex flex-col gap-1">
              <span class="text-xs text-content-tertiary">Mihomo</span>
              <span class="text-sm font-medium inline-flex items-center gap-1.5"
                :class="proxyStatus.mihomoReachable ? 'text-green-600' : 'text-red-500'">
                <span class="inline-block w-2 h-2 rounded-full"
                  :class="proxyStatus.mihomoReachable ? 'bg-green-500' : 'bg-red-500'" />
                {{ proxyStatus.mihomoReachable ? '可达' : '不可达' }}
              </span>
            </div>
            <div class="flex flex-col gap-1">
              <span class="text-xs text-content-tertiary">订阅</span>
              <span class="text-sm font-medium" :class="proxyStatus.subscriptionUrl ? 'text-green-600' : 'text-content-tertiary'">
                {{ proxyStatus.subscriptionUrl ? '已配置' : '未配置' }}
              </span>
            </div>
          </div>

          <div v-if="proxyStatus?.message && !proxyStatus.mihomoReachable" class="mt-3">
            <el-alert :title="proxyStatus.message" type="warning" :closable="false" show-icon />
          </div>

          <div v-if="!proxyStatus && !loading" class="text-sm text-content-tertiary">
            代理状态暂不可用
          </div>
        </div>
      </div>

      </template>

      <!-- Empty State -->
      <div v-if="!loading && configs.length === 0" class="py-20 text-center">
        <el-empty description="暂无配置数据" />
      </div>
    </div>
  </div>
</template>
