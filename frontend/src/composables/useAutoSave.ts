import { ref, watch, onBeforeUnmount, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onBeforeRouteLeave } from 'vue-router'
import { POLLING_INTERVAL } from '@/constants/api'

/**
 * 自动草稿保存 composable
 *
 * 将表单数据定期保存到 localStorage，支持恢复、清除和未保存离开提示。
 *
 * @param form - 响应式表单对象（reactive）
 * @param options.draftKey - localStorage 中的草稿 key
 * @param options.intervalMs - 自动保存间隔，默认 30000ms
 * @param options.maxAgeHours - 草稿最大保留时长，默认 24 小时
 */
export function useAutoSave<T extends Record<string, unknown>>(
  form: T,
  options: {
    draftKey: string
    intervalMs?: number
    maxAgeHours?: number
  },
) {
  const DRAFT_KEY = options.draftKey
  const DRAFT_TIME_KEY = `${options.draftKey}_time`
  const intervalMs = options.intervalMs ?? POLLING_INTERVAL.AUTO_SAVE
  const maxAgeHours = options.maxAgeHours ?? 24

  let autoSaveInterval: number | null = null

  const hasUnsavedChanges = ref(false)
  // 初始化保护：首次挂载后的数据加载不应触发未保存标记
  const isReady = ref(false)
  // 恢复草稿期间不标记变化
  const isRestoring = ref(false)
  // 恢复草稿弹窗是否打开，防止与路由离开守卫弹窗堆叠
  const isRestoreDialogOpen = ref(false)

  // 监听表单变化（跳过初始化阶段和恢复草稿阶段，避免误触发）
  watch(
    form,
    () => {
      if (!isReady.value || isRestoring.value) return
      hasUnsavedChanges.value = true
    },
    { deep: true, flush: 'post' },
  )

  // 浏览器原生离开提示
  function handleBeforeUnload(e: BeforeUnloadEvent): void {
    if (hasUnsavedChanges.value) {
      e.preventDefault()
      e.returnValue = ''
    }
  }

  // 恢复草稿
  function restoreDraft(): void {
    const draft = localStorage.getItem(DRAFT_KEY)
    const draftTime = localStorage.getItem(DRAFT_TIME_KEY)
    if (draft && draftTime) {
      const hours = (Date.now() - parseInt(draftTime)) / 3600000
      if (hours < maxAgeHours) {
        isRestoreDialogOpen.value = true
        ElMessageBox.confirm('检测到有未提交的草稿，是否恢复？', '提示', {
          confirmButtonText: '恢复',
          cancelButtonText: '放弃',
          type: 'info',
        })
          .then(() => {
            isRestoring.value = true
            const draftData = JSON.parse(draft)
            Object.assign(form, draftData)
            nextTick(() => { isRestoring.value = false })
            ElMessage.success('草稿已恢复')
          })
          .catch(() => {
            clearDraft()
          })
          .finally(() => {
            isRestoreDialogOpen.value = false
          })
      } else {
        clearDraft()
      }
    }
  }

  // 自动保存（仅在有未保存变更时写入）
  function startAutoSave(): void {
    autoSaveInterval = window.setInterval(() => {
      if ((form.title || form.content) && hasUnsavedChanges.value) {
        localStorage.setItem(DRAFT_KEY, JSON.stringify(form))
        localStorage.setItem(DRAFT_TIME_KEY, Date.now().toString())
      }
    }, intervalMs)
  }

  // 清除草稿
  function clearDraft(): void {
    hasUnsavedChanges.value = false
    localStorage.removeItem(DRAFT_KEY)
    localStorage.removeItem(DRAFT_TIME_KEY)
    if (autoSaveInterval) {
      clearInterval(autoSaveInterval)
      autoSaveInterval = null
    }
  }

  // 标记已保存
  function markSaved(): void {
    hasUnsavedChanges.value = false
  }

  // 手动启用变化监听（在异步数据加载完成后调用，避免误触发）
  function ready(): void {
    isReady.value = true
  }

  // 注册路由离开守卫
  onBeforeRouteLeave((_to, _from, next) => {
    if (isRestoreDialogOpen.value) {
      next(false)
      return
    }
    if (hasUnsavedChanges.value) {
      ElMessageBox.confirm('有未保存的修改，确定要离开吗？', '提示', {
        confirmButtonText: '离开',
        cancelButtonText: '取消',
        type: 'warning',
      })
        .then(() => next())
        .catch(() => next(false))
    } else {
      next()
    }
  })

  // 注册生命周期
  onMounted(() => {
    restoreDraft()
    startAutoSave()
    window.addEventListener('beforeunload', handleBeforeUnload)
  })

  onBeforeUnmount(() => {
    if (autoSaveInterval) {
      clearInterval(autoSaveInterval)
    }
    window.removeEventListener('beforeunload', handleBeforeUnload)
  })

  return { hasUnsavedChanges, clearDraft, markSaved, ready }
}
