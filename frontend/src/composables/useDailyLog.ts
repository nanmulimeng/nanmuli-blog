import { ref, computed } from 'vue'
import {
  getDailyLogList,
  getDailyLogById,
  createDailyLog,
  updateDailyLog,
  deleteDailyLog,
} from '@/api/dailyLog'
import type { DailyLog, DailyLogQuery } from '@/types/dailyLog'

/**
 * 技术日志数据管理组合式函数
 */
export function useDailyLog() {
  const loading = ref(false)
  const logs = ref<DailyLog[]>([])
  const currentLog = ref<DailyLog | null>(null)
  const total = ref(0)

  const logList = computed(() => logs.value)

  async function fetchLogs(query: DailyLogQuery): Promise<void> {
    loading.value = true
    try {
      const res = await getDailyLogList(query)
      logs.value = res.records
      total.value = res.total
    } finally {
      loading.value = false
    }
  }

  async function fetchLogById(id: string): Promise<void> {
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
    } else {
      await createDailyLog(data)
    }
  }

  async function removeLog(id: string): Promise<void> {
    await deleteDailyLog(id)
  }

  return {
    loading,
    logs: logList,
    currentLog,
    total,
    fetchLogs,
    fetchLogById,
    saveLog,
    removeLog,
  }
}
