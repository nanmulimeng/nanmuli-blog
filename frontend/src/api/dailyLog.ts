import { get, post, put, del } from '@/utils/request'
import type { DailyLog, DailyLogQuery } from '@/types/dailyLog'
import type { PageResult } from '@/types/api'

export function getDailyLogList(params: DailyLogQuery): Promise<PageResult<DailyLog>> {
  return get<PageResult<DailyLog>>('/daily-log/list', { params })
}

export function getDailyLogById(id: number): Promise<DailyLog> {
  return get<DailyLog>(`/daily-log/${id}`)
}

export function createDailyLog(data: Partial<DailyLog>): Promise<number> {
  return post<number>('/admin/daily-log', data)
}

export function updateDailyLog(id: number, data: Partial<DailyLog>): Promise<void> {
  return put<void>(`/admin/daily-log/${id}`, data)
}

export function deleteDailyLog(id: number): Promise<void> {
  return del<void>(`/admin/daily-log/${id}`)
}
