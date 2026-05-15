<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshRight, Lock, Hide } from '@element-plus/icons-vue'
import { getAdminConfigList, updateConfig, refreshConfigs, getProxyStatus } from '@/api/config'
import type { Config, ProxyStatus } from '@/types/config'
import FileUpload from '@/components/common/FileUpload.vue'

const loading = ref(false)
const refreshing = ref(false)
const savingSection = ref<string | null>(null)
const configs = ref<Config[]>([])
const formData = ref<Record<string, string>>({})
const originalData = ref<Record<string, string>>({})
const activeTab = ref('crawler')
const proxyStatus = ref<ProxyStatus | null>(null)

// ====== 数据获取 ======

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    configs.value = await getAdminConfigList()
    configs.value.forEach((c) => {
      formData.value[c.configKey] = c.configValue ?? ''
      originalData.value[c.configKey] = c.configValue ?? ''
    })
    await fetchProxyStatus()
  } finally {
    loading.value = false
  }
}

async function fetchProxyStatus(): Promise<void> {
  try { proxyStatus.value = await getProxyStatus() } catch { proxyStatus.value = null }
}

async function handleRefreshAll(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '将刷新 Java ConfigService 缓存、HTTP 连接池和 Python 爬虫服务配置，确定继续？',
      '确认刷新',
      { confirmButtonText: '刷新', cancelButtonText: '取消', type: 'warning' },
    )
  } catch { return }

  refreshing.value = true
  try {
    const result = await refreshConfigs()
    ElMessage.success(result.message || '配置已刷新')
    await fetchData()
  } catch {
    ElMessage.error('刷新失败，请检查后端服务状态')
  } finally {
    refreshing.value = false
  }
}

// ====== 分组逻辑 ======

const SUB_LABELS: Record<string, string> = {
  'ai': 'AI 整理', 'search': '搜索参数', 'quality': '质量评估',
  'digest': '日报', 'auth': '认证', 'optimization': '搜索优化',
  'bubble': '茧房突破', 'callback': '回调', 'db': '数据库',
  'keyword': '关键词', 'limit': '爬取限制', 'proxy': '代理',
  'service': '服务连接', 'http.pool': 'HTTP 连接池',
  '': '基础',
}

function getSubPrefix(key: string): string {
  const parts = key.split('.')
  if (parts.length <= 2) return ''
  if (parts[1] === 'http' && parts[2] === 'pool') return 'http.pool'
  return parts[1] || ''
}

const sortedGroups = computed(() => {
  const groups = new Set(configs.value.map((c) => c.groupName || 'other'))
  const priority = ['crawler', 'site', 'blog']
  const sorted = [...groups].sort((a, b) => {
    const ai = priority.indexOf(a), bi = priority.indexOf(b)
    if (ai !== -1 && bi !== -1) return ai - bi
    if (ai !== -1) return -1
    if (bi !== -1) return 1
    return a.localeCompare(b)
  })
  return sorted
})

const groupedConfigs = computed(() => {
  const result: Record<string, { name: string; label: string; configs: Config[] }[]> = {}
  for (const group of sortedGroups.value) {
    const items = configs.value.filter((c) => (c.groupName || 'other') === group)
    const secMap: Record<string, Config[]> = {}
    items.forEach((c) => {
      const sub = getSubPrefix(c.configKey)
      if (!secMap[sub]) secMap[sub] = []
      secMap[sub]!.push(c)
    })
    const secOrder = Object.keys(SUB_LABELS)
    result[group] = Object.entries(secMap).map(([name, cfgs]) => ({
      name, label: SUB_LABELS[name] || name,
      configs: cfgs.sort((a, b) => a.configKey.localeCompare(b.configKey)),
    })).sort((a, b) => {
      const ai = secOrder.indexOf(a.name), bi = secOrder.indexOf(b.name)
      if (ai === -1 && bi === -1) return a.name.localeCompare(b.name)
      if (ai === -1) return 1; if (bi === -1) return -1; return ai - bi
    })
  }
  return result
})

// ====== 保存逻辑 ======

async function handleSave(key: string): Promise<void> {
  const value = formData.value[key]
  if (value === undefined || value === originalData.value[key]) return
  try {
    await updateConfig(key, value)
    originalData.value[key] = value
    ElMessage.success('已保存')
    if (key.startsWith('crawler.proxy.')) await fetchProxyStatus()
  } catch { ElMessage.error('保存失败') }
}

async function handleSaveSection(group: string, sectionName: string): Promise<void> {
  const sections = groupedConfigs.value[group]
  if (!sections) return
  const section = sections.find((s) => s.name === sectionName)
  if (!section) return

  savingSection.value = `${group}/${sectionName}`
  let saved = 0; let skipped = 0; let failed = 0
  try {
    for (const config of section.configs) {
      const value = formData.value[config.configKey]
      if ((config.isSensitive || config.sensitive) && value === '********') { skipped++; continue }
      if (value === undefined || value === originalData.value[config.configKey]) { skipped++; continue }
      try { await updateConfig(config.configKey, value); saved++; originalData.value[config.configKey] = value } catch { failed++ }
    }
    const parts = [saved && `保存 ${saved}`, skipped && `跳过 ${skipped}`, failed && `失败 ${failed}`].filter(Boolean)
    ElMessage.success(parts.length ? parts.join(' / ') : '无变更')
    if (sectionName === 'proxy') await fetchProxyStatus()
  } catch { ElMessage.error('保存失败') }
  finally { savingSection.value = null }
}

// ====== 辅助 ======

function getInputType(config: Config): 'text' | 'textarea' | 'switch' | 'image' | 'password' {
  const valid = ['text', 'textarea', 'switch', 'image', 'password'] as const
  const t = config.inputType || 'text'
  return valid.includes(t as typeof valid[number]) ? (t as typeof valid[number]) : 'text'
}

function shortLabel(key: string): string {
  const parts = key.split('.')
  return parts.length > 1 ? parts.slice(1).join('.') : key
}

function handleImageChange(key: string, url: string): void {
  formData.value[key] = url
  handleSave(key)
}

function isMasked(config: Config): boolean {
  return !!(config.isSensitive || config.sensitive) && formData.value[config.configKey] === '********'
}

onMounted(fetchData)
</script>

<template>
  <div>
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-content-primary">系统配置</h2>
        <p class="mt-1 text-sm text-content-tertiary">
          管理网站与爬虫全量配置项，修改后自动生效
        </p>
      </div>
      <div class="flex gap-2">
        <el-button
          type="warning"
          :icon="RefreshRight"
          :loading="refreshing"
          @click="handleRefreshAll"
        >
          刷新后端缓存
        </el-button>
        <el-button :icon="RefreshRight" :loading="loading" @click="fetchData">
          重新加载
        </el-button>
      </div>
    </div>

    <!-- Tabs -->
    <div v-loading="loading">
      <el-tabs v-model="activeTab" type="border-card" v-if="sortedGroups.length > 0">
        <el-tab-pane
          v-for="group in sortedGroups"
          :key="group"
          :label="group"
          :name="group"
        >
          <div class="space-y-6">
            <div
              v-for="section in groupedConfigs[group]"
              :key="section.name"
              class="rounded-xl border border-border bg-surface p-4"
            >
              <!-- Section Header -->
              <div class="flex items-center justify-between mb-4 pb-2 border-b border-border">
                <div>
                  <h3 class="text-base font-semibold text-content-primary">
                    {{ section.label }}
                  </h3>
                  <p class="text-xs text-content-tertiary mt-0.5">
                    {{ section.configs.length }} 项
                  </p>
                </div>
                <el-button
                  size="small"
                  type="primary"
                  :loading="savingSection === `${group}/${section.name}`"
                  @click="handleSaveSection(group, section.name)"
                >
                  保存本组
                </el-button>
              </div>

              <!-- Config Items -->
              <div class="space-y-4">
                <div
                  v-for="config in section.configs"
                  :key="config.configKey"
                  class="flex flex-col gap-2 sm:flex-row sm:items-start"
                >
                  <!-- Label -->
                  <div class="w-full sm:w-44 flex-shrink-0 pt-1.5">
                    <label class="text-sm font-medium text-content-primary">
                      {{ config.description || shortLabel(config.configKey) }}
                    </label>
                    <p class="mt-0.5 text-xs text-content-tertiary font-mono break-all">
                      {{ config.configKey }}
                    </p>
                    <!-- Badges -->
                    <div class="mt-1 flex flex-wrap gap-1">
                      <el-tag v-if="config.isEncrypted" type="info" size="small" effect="plain">
                        <el-icon :size="12"><Lock /></el-icon>
                        加密
                      </el-tag>
                      <el-tag v-if="config.isSensitive || config.sensitive" type="warning" size="small" effect="plain">
                        <el-icon :size="12"><Hide /></el-icon>
                        敏感
                      </el-tag>
                    </div>
                  </div>

                  <!-- Input -->
                  <div class="flex-1 min-w-0">
                    <!-- Switch -->
                    <template v-if="getInputType(config) === 'switch'">
                      <div class="flex items-center gap-3">
                        <el-switch
                          :model-value="formData[config.configKey]"
                          active-value="true"
                          inactive-value="false"
                          @change="(val) => { formData[config.configKey] = String(val); handleSave(config.configKey) }"
                        />
                        <span class="text-sm text-content-secondary">
                          {{ formData[config.configKey] === 'true' ? '已启用' : '已禁用' }}
                        </span>
                      </div>
                    </template>

                    <!-- Image -->
                    <template v-else-if="getInputType(config) === 'image'">
                      <FileUpload
                        :model-value="formData[config.configKey] || ''"
                        placeholder="输入图片 URL 或点击上传"
                        @update:model-value="(url) => handleImageChange(config.configKey, url)"
                      />
                    </template>

                    <!-- Password -->
                    <template v-else-if="getInputType(config) === 'password' && !isMasked(config)">
                      <el-input
                        v-model="formData[config.configKey]"
                        type="password"
                        show-password
                        :placeholder="config.defaultValue || `输入 ${config.description || shortLabel(config.configKey)}`"
                        @blur="handleSave(config.configKey)"
                      />
                    </template>

                    <!-- Masked sensitive -->
                    <template v-else-if="getInputType(config) === 'password' && isMasked(config)">
                      <div class="flex items-center gap-2">
                        <el-input
                          v-model="formData[config.configKey]"
                          disabled
                          class="!w-48"
                        />
                        <el-button size="small" @click="formData[config.configKey] = ''">
                          重新输入
                        </el-button>
                      </div>
                    </template>

                    <!-- Textarea -->
                    <template v-else-if="getInputType(config) === 'textarea'">
                      <el-input
                        v-model="formData[config.configKey]"
                        type="textarea"
                        :rows="config.configKey.includes('sections') ? 6 : 3"
                        :placeholder="config.defaultValue || `输入 ${config.description || ''}`"
                        @blur="handleSave(config.configKey)"
                      />
                    </template>

                    <!-- Text -->
                    <template v-else>
                      <el-input
                        v-model="formData[config.configKey]"
                        clearable
                        :placeholder="config.defaultValue || `输入 ${config.description || shortLabel(config.configKey)}`"
                        @blur="handleSave(config.configKey)"
                      />
                    </template>
                  </div>
                </div>
              </div>
            </div>

            <!-- Proxy Status Card -->
            <div
              v-if="proxyStatus && groupedConfigs[group]?.some(s => s.name === 'proxy')"
              class="rounded-xl border border-border bg-surface p-4"
            >
              <div class="flex items-center justify-between mb-3">
                <h4 class="text-sm font-semibold text-content-primary">代理状态</h4>
                <router-link to="/admin/proxy" class="text-xs text-primary hover:underline">
                  前往代理管理 →
                </router-link>
              </div>
              <div class="grid grid-cols-3 gap-4">
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
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <el-empty v-if="!loading && configs.length === 0" description="暂无配置数据" />
    </div>
  </div>
</template>
