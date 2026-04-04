import type { PageQuery } from './api'

export interface DailyLog {
  id: number
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
