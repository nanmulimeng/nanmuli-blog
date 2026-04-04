import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getDailyLogList,
  getDailyLogById,
  createDailyLog,
  updateDailyLog,
  deleteDailyLog,
} from '@/api/dailyLog'
import type { DailyLog, DailyLogQuery } from '@/types/dailyLog'
import type { PageResult } from '@/types/api'

/**
 * 技术日志状态管理 Store
 */
export const useDailyLogStore = defineStore(
  'dailyLog',
  () => {
    // State
    const logs = ref<DailyLog[]>([])
    const currentLog = ref<DailyLog | null>(null)
    const loading = ref(false)
    const pagination = ref({
      current: 1,
      size: 10,
      total: 0,
    })

    // Getters
    const logList = computed(() => logs.value)
    const hasCurrentLog = computed(() => currentLog.value !== null)

    // 按日期分组的日志（用于时间线展示）
    const groupedLogs = computed(() => {
      const groups: Record<string, DailyLog[]> = {}
      logs.value.forEach((log) => {
        const date = log.logDate.split('T')[0]
        if (!groups[date]) {
          groups[date] = []
        }
        groups[date].push(log)
      })
      // 按日期降序排列
      return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]))
    })

    // Actions
    async function fetchLogs(query?: DailyLogQuery): Promise<void> {
      loading.value = true
      try {
        const params: DailyLogQuery = {
          current: pagination.value.current,
          size: pagination.value.size,
          ...query,
        }
        const result: PageResult<DailyLog> = await getDailyLogList(params)
        logs.value = result.records
        pagination.value.total = result.total
      } finally {
        loading.value = false
      }
    }

    async function fetchLogById(id: number): Promise<void> {
      loading.value = true
      try {
        currentLog.value = await getDailyLogById(id)
      } finally {
        loading.value = false
      }
    }

    async function saveLog(data: Partial<DailyLog>): Promise<void> {
      if (data.id) {
        await updateDailyLog(data.id, data)
        // 更新本地数据
        const index = logs.value.findIndex((l) => l.id === data.id)
        if (index !== -1) {
          logs.value[index] = { ...logs.value[index], ...data } as DailyLog
        }
      } else {
        await createDailyLog(data)
      }
    }

    async function removeLog(id: number): Promise<void> {
      await deleteDailyLog(id)
      logs.value = logs.value.filter((l) => l.id !== id)
    }

    function setCurrentLog(log: DailyLog | null): void {
      currentLog.value = log
    }

    function updatePagination(current: number, size?: number): void {
      pagination.value.current = current
      if (size) pagination.value.size = size
    }

    function $reset(): void {
      logs.value = []
      currentLog.value = null
      pagination.value = { current: 1, size: 10, total: 0 }
    }

    return {
      // State
      logs,
      currentLog,
      loading,
      pagination,
      // Getters
      logList,
      hasCurrentLog,
      groupedLogs,
      // Actions
      fetchLogs,
      fetchLogById,
      saveLog,
      removeLog,
      setCurrentLog,
      updatePagination,
      $reset,
    }
  }
)
