import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

// ==================== 中文格式时间函数 ====================

/**
 * 格式化日期为中文格式：YYYY年M月D日
 */
export function formatDateCN(date: string | Date | undefined): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY年M月D日')
}

/**
 * 格式化为短日期：M月D日
 */
export function formatShortDateCN(date: string | Date | undefined): string {
  if (!date) return '-'
  return dayjs(date).format('M月D日')
}

/**
 * 格式化月份：YYYY年M月
 */
export function formatMonthCN(date: string | undefined): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY年M月')
}

/**
 * 格式化完整时间：YYYY年M月D日 HH:mm:ss
 */
export function formatDateTimeCN(date: string | Date | undefined): string {
  if (!date) return '-'
  return dayjs(date).format('YYYY年M月D日 HH:mm:ss')
}

/**
 * 相对时间：刚刚、5分钟前、2小时前、昨天、3天前...
 */
export function fromNowCN(date: string | Date | undefined): string {
  if (!date) return '-'

  const now = dayjs()
  const target = dayjs(date)
  const diffMinutes = now.diff(target, 'minute')
  const diffHours = now.diff(target, 'hour')
  const diffDays = now.diff(target, 'day')

  if (diffMinutes < 1) return '刚刚'
  if (diffMinutes < 60) return `${diffMinutes}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) return `${diffDays}天前`

  return formatDateCN(date)
}

// ==================== 数字格式化 ====================

/**
 * 数字千分位分隔
 */
export function formatNumber(num: number | undefined): string {
  if (num === undefined || num === null) return '0'
  return num.toLocaleString('zh-CN')
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// ==================== 向后兼容的旧函数 (不推荐) ====================

/** @deprecated 使用 formatDateCN */
export function formatDate(date: string | Date, format = 'YYYY-MM-DD'): string {
  return dayjs(date).format(format)
}

/** @deprecated 使用 formatDateTimeCN */
export function formatDateTime(date: string | Date): string {
  return dayjs(date).format('YYYY年M月D日 HH:mm')
}

/** @deprecated 使用 fromNowCN */
export function fromNow(date: string | Date): string {
  return fromNowCN(date)
}
