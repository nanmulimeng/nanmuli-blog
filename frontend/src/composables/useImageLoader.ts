import { reactive } from 'vue'

/**
 * 图片加载状态追踪（用于程序化图片处理场景，如 markdown v-html）
 * SrcImage 组件内置了同等逻辑，模板中优先使用 SrcImage 组件
 */
export function useImageLoader() {
  const loadedMap = reactive<Record<string, boolean>>({})

  function markResolved(key: string) {
    loadedMap[key] = true
  }

  function isLoaded(key: string): boolean {
    return loadedMap[key] ?? false
  }

  function reset(key?: string) {
    if (key) {
      delete loadedMap[key]
    } else {
      Object.keys(loadedMap).forEach(k => delete loadedMap[k])
    }
  }

  return { loadedMap, markResolved, isLoaded, reset }
}
