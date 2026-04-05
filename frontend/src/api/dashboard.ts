import { get } from '@/utils/request'
import type { Article } from '@/types/article'

export interface DashboardStats {
  articleCount: number
  categoryCount: number
  tagCount: number
  viewCount: number
}

export function getDashboardStats(): Promise<DashboardStats> {
  return get<DashboardStats>('/admin/dashboard/stats')
}

export function getRecentArticles(limit: number = 5): Promise<Article[]> {
  return get<Article[]>(`/admin/dashboard/recent-articles?limit=${limit}`)
}
