import type { PageQuery } from './api'

// 注意：ID 使用 string 类型，因为 JavaScript number 无法精确表示 64 位整数
export interface DailyLog {
  id: string
  content: string
  contentHtml: string
  mood: 'happy' | 'excited' | 'normal' | 'tired'
  weather: string
  tags: string[]
  wordCount: number
  logDate: string
  createTime: string
  updateTime: string
}

export interface DailyLogQuery extends PageQuery {
  startDate?: string
  endDate?: string
}

export interface DailyLogForm {
  logDate: string
  mood: 'happy' | 'excited' | 'normal' | 'tired'
  weather: string
  content: string
  tagIds: string[]
}
