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
function fromNowCN(date: string | Date | undefined): string {
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

// ==================== 向后兼容的旧函数 (不推荐) ====================

/** @deprecated 使用 formatDateCN */
export function formatDate(date: string | Date, format = 'YYYY-MM-DD'): string {
  return dayjs(date).format(format)
}

/** 相对时间别名：刚刚、5分钟前、2小时前... */
export const formatTimeAgoCN = fromNowCN
