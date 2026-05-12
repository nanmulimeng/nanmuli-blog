<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight, Connection } from '@element-plus/icons-vue'
import {
  getProxyStatus,
  getProxyGroups,
  selectProxy,
  testNodesDelay,
  getSubscriptionUrl,
  updateSubscriptionUrl,
  refreshSubscription,
  updateConfig,
} from '@/api/config'
import type { ProxyStatus, ProxyGroup, NodeDelay } from '@/types/config'

const loading = ref(false)
const status = ref<ProxyStatus | null>(null)
const groups = ref<ProxyGroup[]>([])
const delays = ref<Record<string, Record<string, number>>>({})
const testingGroup = ref<string | null>(null)
const selectingNode = ref<string | null>(null)
const subUrl = ref('')
const savingSub = ref(false)
const refreshingSub = ref(false)

async function fetchAll(): Promise<void> {
  loading.value = true
  try {
    const [s, g, sub] = await Promise.all([
      getProxyStatus().catch(() => null),
      getProxyGroups().catch(() => []),
      getSubscriptionUrl().catch(() => ''),
    ])
    status.value = s
    groups.value = g
    subUrl.value = sub
  } finally {
    loading.value = false
  }
}

async function handleTestDelay(groupName: string): Promise<void> {
  testingGroup.value = groupName
  try {
    const results: NodeDelay[] = await testNodesDelay(groupName)
    const groupDelays: Record<string, number> = {}
    results.forEach((r) => {
      groupDelays[r.nodeName] = r.reachable ? r.delay : 0
    })
    delays.value[groupName] = groupDelays
    ElMessage.success('延迟测试完成')
  } catch {
    ElMessage.error('延迟测试失败，Mihomo 服务不可达')
  } finally {
    testingGroup.value = null
  }
}

async function handleSelectNode(groupName: string, nodeName: string): Promise<void> {
  selectingNode.value = `${groupName}::${nodeName}`
  try {
    await selectProxy(groupName, nodeName)
    // 更新本地状态
    const group = groups.value.find((g) => g.name === groupName)
    if (group) {
      ;(group as { now: string }).now = nodeName
    }
    ElMessage.success(`已切换到 ${nodeName}`)
  } catch {
    ElMessage.error('节点切换失败，Mihomo 服务不可达')
  } finally {
    selectingNode.value = null
  }
}

async function handleSaveSubscription(): Promise<void> {
  savingSub.value = true
  try {
    await updateSubscriptionUrl(subUrl.value)
    ElMessage.success('订阅地址已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingSub.value = false
  }
}

async function handleRefreshSubscription(): Promise<void> {
  refreshingSub.value = true
  try {
    await refreshSubscription()
    ElMessage.success('订阅刷新中，请稍后刷新查看节点')
  } catch {
    ElMessage.error('订阅刷新失败，Mihomo 服务不可达')
  } finally {
    refreshingSub.value = false
  }
}

function getDelayColor(delay: number | undefined): string {
  if (delay === undefined || delay === 0) return 'info'
  if (delay < 100) return 'success'
  if (delay < 300) return 'warning'
  return 'danger'
}

function getDelayText(delay: number | undefined): string {
  if (delay === undefined) return '未测试'
  if (delay === 0) return '不可达'
  return `${delay}ms`
}

function getNodeDelay(groupName: string, nodeName: string): number | undefined {
  const groupDelays = delays.value[groupName]
  if (!groupDelays) return undefined
  return groupDelays[nodeName]
}

onMounted(fetchAll)
</script>

<template>
  <div>
    <!-- 页面标题 -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-content-primary">代理管理</h2>
        <p class="mt-1 text-sm text-content-tertiary">
          管理 Mihomo 代理节点、测试延迟、配置订阅地址
        </p>
      </div>
      <el-button type="primary" :icon="RefreshRight" :loading="loading" @click="fetchAll">
        刷新
      </el-button>
    </div>

    <div v-loading="loading" class="space-y-6">
      <!-- 订阅地址 -->
      <div class="rounded-2xl border border-border bg-surface-secondary p-6 shadow-sm">
        <h3 class="text-sm font-semibold text-content-primary mb-4 flex items-center gap-2">
          <el-icon><Connection /></el-icon>
          订阅地址
        </h3>
        <div class="flex gap-3">
          <el-input
            v-model="subUrl"
            placeholder="输入订阅 URL，如 https://example.com/subscription"
            clearable
            class="flex-1"
          />
          <el-button type="primary" :loading="savingSub" @click="handleSaveSubscription">
            保存
          </el-button>
          <el-button :loading="refreshingSub" @click="handleRefreshSubscription">
            更新订阅
          </el-button>
        </div>
        <p class="mt-2 text-xs text-content-tertiary">
          订阅地址保存后同时更新到 Mihomo，点击「更新订阅」重新拉取节点列表
        </p>
      </div>

      <!-- 代理状态概览 -->
      <div
        v-if="status"
        class="rounded-2xl border border-border bg-surface-secondary p-6 shadow-sm"
      >
        <h3 class="text-sm font-semibold text-content-primary mb-4">状态概览</h3>
        <div class="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <div class="flex flex-col gap-1">
            <span class="text-xs text-content-tertiary">启用状态</span>
            <span
              class="text-sm font-medium"
              :class="status.enabled ? 'text-green-600' : 'text-content-tertiary'"
            >
              {{ status.enabled ? '已启用' : '未启用' }}
            </span>
          </div>
          <div class="flex flex-col gap-1">
            <span class="text-xs text-content-tertiary">代理地址</span>
            <span class="text-sm font-medium text-content-primary truncate" :title="status.url">
              {{ status.url || '未配置' }}
            </span>
          </div>
          <div class="flex flex-col gap-1">
            <span class="text-xs text-content-tertiary">Mihomo 状态</span>
            <span
              class="text-sm font-medium inline-flex items-center gap-1.5"
              :class="status.mihomoReachable ? 'text-green-600' : 'text-red-500'"
            >
              <span
                class="inline-block w-2 h-2 rounded-full"
                :class="status.mihomoReachable ? 'bg-green-500' : 'bg-red-500'"
              />
              {{ status.mihomoReachable ? '可达' : '不可达' }}
            </span>
          </div>
          <div v-if="status.latencyMs !== undefined" class="flex flex-col gap-1">
            <span class="text-xs text-content-tertiary">Mihomo 延迟</span>
            <span class="text-sm font-medium text-content-primary">
              {{ status.latencyMs }}ms
            </span>
          </div>
          <div class="flex flex-col gap-1">
            <span class="text-xs text-content-tertiary">代理组数量</span>
            <span class="text-sm font-medium text-content-primary">
              {{ groups.length }}
            </span>
          </div>
        </div>
        <div v-if="status.message && !status.mihomoReachable" class="mt-3">
          <el-alert :title="status.message" type="warning" :closable="false" show-icon />
        </div>
      </div>

      <!-- 代理组列表 -->
      <template v-if="groups.length > 0">
        <div
          v-for="group in groups"
          :key="group.name"
          class="rounded-2xl border border-border bg-surface-secondary p-6 shadow-sm"
        >
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-3">
              <h3 class="text-sm font-semibold text-content-primary">{{ group.name }}</h3>
              <el-tag size="small" :type="group.type === 'Selector' ? 'primary' : 'info'">
                {{ group.type }}
              </el-tag>
              <span class="text-xs text-content-tertiary">
                当前: <span class="text-content-primary font-medium">{{ group.now }}</span>
              </span>
            </div>
            <el-button
              size="small"
              :loading="testingGroup === group.name"
              @click="handleTestDelay(group.name)"
            >
              测试全部延迟
            </el-button>
          </div>

          <el-table :data="group.nodes" size="small" stripe>
            <el-table-column prop="name" label="节点名称" min-width="200">
              <template #default="{ row }">
                <span class="text-sm">{{ row.name }}</span>
                <el-tag v-if="row.name === group.now" size="small" type="success" class="ml-2">
                  当前
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="延迟" width="120" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="getDelayColor(getNodeDelay(group.name, row.name))"
                  size="small"
                  effect="plain"
                >
                  {{ getDelayText(getNodeDelay(group.name, row.name)) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" align="center">
              <template #default="{ row }">
                <el-button
                  v-if="row.name !== group.now"
                  size="small"
                  type="primary"
                  :loading="selectingNode === `${group.name}::${row.name}`"
                  :disabled="selectingNode !== null"
                  @click="handleSelectNode(group.name, row.name)"
                >
                  选择
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>

      <!-- Mihomo 不可达占位 -->
      <div
        v-if="!loading && status && !status.mihomoReachable"
        class="py-12 text-center rounded-2xl border border-border bg-surface-secondary"
      >
        <el-empty description="Mihomo 代理服务不可达">
          <template #image>
            <el-icon :size="64" class="text-content-tertiary"><Connection /></el-icon>
          </template>
        </el-empty>
        <p class="mt-1 text-sm text-content-tertiary">
          请确保 Mihomo 已安装并运行（默认端口 9090）
        </p>
      </div>
    </div>
  </div>
</template>
