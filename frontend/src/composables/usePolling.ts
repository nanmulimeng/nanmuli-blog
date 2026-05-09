import { ref, onUnmounted } from 'vue'
import { POLLING_INTERVAL } from '@/constants/api'

/**
 * 轮询 composable — 使用递归 setTimeout 避免慢网络下请求堆叠
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
  let timer: ReturnType<typeof setTimeout> | null = null
  let running = false

  const immediate = options?.immediate ?? true
  const condition = options?.condition

  async function poll(): Promise<void> {
    if (running) return
    if (condition && !condition()) {
      stop()
      return
    }
    running = true
    isPolling.value = true
    try {
      await fn()
    } finally {
      running = false
      isPolling.value = false
    }

    // 执行完成后调度下一轮（而非固定间隔，避免请求堆叠）
    if (timer !== null) {
      timer = setTimeout(poll, intervalMs) as unknown as ReturnType<typeof setTimeout>
    }
  }

  function start(): void {
    if (timer !== null) return
    if (immediate) {
      poll()
      // poll 完成后会自动调度下一轮
    } else {
      timer = setTimeout(poll, intervalMs) as unknown as ReturnType<typeof setTimeout>
    }
  }

  function stop(): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
    running = false
    isPolling.value = false
  }

  onUnmounted(() => stop())

  return { isPolling, start, stop }
}
