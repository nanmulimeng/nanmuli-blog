import { get, post, del } from '@/utils/request'
import type { CollectTask, CollectTaskListDTO, CollectPage, CreateCollectTaskCommand, ConvertToArticleCommand, ConvertToDailyLogCommand, CollectTaskQuery } from '@/types/collector'
import type { PageResult } from '@/types/api'

// 创建采集任务
export function createCollectTask(data: CreateCollectTaskCommand): Promise<Record<string, any>> {
  return post<Record<string, any>>('/admin/collector/task', data)
}

// 获取任务列表
export function getCollectTaskList(params: CollectTaskQuery): Promise<PageResult<CollectTaskListDTO>> {
  return get<PageResult<CollectTaskListDTO>>('/admin/collector/task/list', { params })
}

// 获取任务详情
export function getCollectTaskDetail(taskId: string): Promise<CollectTask> {
  return get<CollectTask>(`/admin/collector/task/${taskId}`)
}

// 获取任务页面列表
export function getCollectTaskPages(taskId: string): Promise<CollectPage[]> {
  return get<CollectPage[]>(`/admin/collector/task/${taskId}/pages`)
}

// 删除任务
export function deleteCollectTask(taskId: string): Promise<void> {
  return del<void>(`/admin/collector/task/${taskId}`)
}

// 重试失败任务
export function retryCollectTask(taskId: string): Promise<string> {
  return post<string>(`/admin/collector/task/${taskId}/retry`)
}

// 转为文章草稿
export function convertToArticle(taskId: string, data: ConvertToArticleCommand): Promise<string> {
  return post<string>(`/admin/collector/task/${taskId}/to-article`, data)
}

// 转为技术日志
export function convertToDailyLog(taskId: string, data: ConvertToDailyLogCommand): Promise<string> {
  return post<string>(`/admin/collector/task/${taskId}/to-daily-log`, data)
}

// 爬虫服务健康检查
export function checkCrawlerHealth(): Promise<Record<string, any>> {
  return get<Record<string, any>>('/admin/collector/crawler/health')
}
