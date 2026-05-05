import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

// 扩展 AxiosRequestConfig 类型以支持重试计数和取消信号
declare module 'axios' {
  interface AxiosRequestConfig {
    __retryCount?: number
    __cleanup?: () => void
  }
}

// 请求取消控制器映射
const pendingControllers = new Map<string, AbortController>()

// 生成请求唯一标识
function generateRequestKey(config: AxiosRequestConfig): string {
  return `${config.method}_${config.url}_${JSON.stringify(config.params)}_${JSON.stringify(config.data)}`
}

const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 最大重试次数
const MAX_RETRIES = 3

// 指数退避延迟计算
function getRetryDelay(retryCount: number): number {
  // 1s, 2s, 4s
  return Math.pow(2, retryCount) * 1000
}

request.interceptors.request.use(
  (config) => {
    // Sa-Token Cookie模式：Token自动随Cookie发送，无需手动设置Header
    // 如需跨域，确保后端配置了CORS允许credentials

    // 添加取消控制器
    if (!config.signal) {
      const controller = new AbortController()
      config.signal = controller.signal
      const key = generateRequestKey(config)

      // 取消重复请求
      if (pendingControllers.has(key)) {
        pendingControllers.get(key)?.abort('重复请求被取消')
      }
      pendingControllers.set(key, controller)

      // 请求完成后清理
      config.__cleanup = () => pendingControllers.delete(key)
    }

    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

request.interceptors.response.use(
  (response) => {
    // 清理请求控制器
    const config = response.config
    if ((config as any).__cleanup) {
      (config as any).__cleanup()
    }

    const { data } = response

    if (data.code !== 200) {
      ElMessage.error(data.message || '请求失败')

      if (data.code === 401 && !window.location.pathname.includes('/login')) {
        // Cookie模式下Token由浏览器自动管理，无需手动清除
        window.location.href = '/login'
      }

      return Promise.reject(new Error(data.message))
    }

    return data.data
  },
  async (error: AxiosError<{ message?: string }>) => {
    const config = error.config

    // 清理请求控制器
    if (config?.__cleanup) {
      config.__cleanup()
    }

    // 初始化重试计数
    if (config && !config.__retryCount) {
      config.__retryCount = 0
    }

    // 重试逻辑：仅对 5xx 错误和网络错误进行重试
    const shouldRetry =
      config &&
      config.__retryCount !== undefined &&
      config.__retryCount < MAX_RETRIES &&
      (!error.response || (error.response.status >= 500 && error.response.status < 600))

    if (shouldRetry && config) {
      const retryCount = (config.__retryCount || 0) + 1
      config.__retryCount = retryCount
      const delay = getRetryDelay(retryCount)

      await new Promise((resolve) => setTimeout(resolve, delay))
      return request(config)
    }

    // 重试次数耗尽或不需要重试，显示错误
    const message = error.response?.data?.message || error.message || '网络错误'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export function get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return request.get(url, config) as Promise<T>
}

export function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return request.post(url, data, config) as Promise<T>
}

export function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return request.put(url, data, config) as Promise<T>
}

export function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return request.delete(url, config) as Promise<T>
}
