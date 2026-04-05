<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getAdminConfigList, updateConfig } from '@/api/config'
import type { Config } from '@/types/config'

const loading = ref(false)
const configs = ref<Config[]>([])
const formData = ref<Record<string, string>>({})

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    configs.value = await getAdminConfigList()
    configs.value.forEach((config) => {
      formData.value[config.configKey] = config.configValue
    })
  } finally {
    loading.value = false
  }
}

async function handleSave(key: string): Promise<void> {
  try {
    const value = formData.value[key]
    if (value === undefined) return
    await updateConfig(key, value)
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败')
  }
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
    const arr = groups[group] || []
    arr.push(config)
    groups[group] = arr
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
    </div>
  </div>
</template>
