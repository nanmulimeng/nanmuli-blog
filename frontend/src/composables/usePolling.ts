import { ref, onUnmounted } from 'vue'
import { POLLING_INTERVAL } from '@/constants/api'

/**
 * 轮询 composable — 统一管理 setInterval 轮询逻辑
 *
 * @param fn - 要定时执行的异步函数
 * @param intervalMs - 轮询间隔（毫秒），默认 5000
 * @param options.immediate - 是否在 start() 时立即执行一次，默认 true
 * @param options.condition - 返回 false 时跳过本轮执行（可用于 "无活跃任务则跳过" 场景）
 */
export function usePolling(
  fn: () => Promise<void>,
  intervalMs: number = POLLING_INTERVAL.TASK_STATUS,
  options?: {
    immediate?: boolean
    condition?: () => boolean
  },
) {
  const isPolling = ref(false)
  let timer: ReturnType<typeof setInterval> | null = null

  const immediate = options?.immediate ?? true
  const condition = options?.condition

  async function poll(): Promise<void> {
    if (condition && !condition()) {
      // 条件不满足时自动停止
      stop()
      return
    }
    if (isPolling.value) return
    isPolling.value = true
    try {
      await fn()
    } finally {
      isPolling.value = false
    }
  }

  function start(): void {
    if (timer) return
    if (immediate) poll()
    timer = setInterval(poll, intervalMs)
  }

  function stop(): void {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onUnmounted(() => stop())

  return { isPolling, start, stop }
}
