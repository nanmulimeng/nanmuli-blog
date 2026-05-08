import { get, post, del } from '@/utils/request'
import type { CollectTask, CollectTaskListDTO, CollectPage, CreateCollectTaskCommand, ConvertToArticleCommand, ConvertToDailyLogCommand, CollectTaskQuery, DigestListResult, DigestDetail, DigestSchedulerStatus, DigestSectionConfig } from '@/types/collector'
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

// ============== Digest API ==============

// 日报列表
export function getDigestList(page = 1, size = 10): Promise<DigestListResult> {
  return get<DigestListResult>('/admin/collector/digest', { params: { page, size } })
}

// 最近一期日报
export function getLatestDigest(): Promise<DigestDetail> {
  return get<DigestDetail>('/admin/collector/digest/latest')
}

// 按日期查询日报
export function getDigestByDate(date: string): Promise<DigestDetail> {
  return get<DigestDetail>(`/admin/collector/digest/${date}`)
}

// 按任务 ID 查询日报
export function getDigestByTaskId(taskId: number): Promise<DigestDetail> {
  return get<DigestDetail>(`/admin/collector/digest/task/${taskId}`)
}

// 手动触发日报生成
export function triggerDigest(force = false): Promise<{ message: string }> {
  return post<{ message: string }>('/admin/collector/digest/trigger', undefined, { params: { force } })
}

// 获取调度器状态
export function getDigestSchedulerStatus(): Promise<DigestSchedulerStatus> {
  return get<DigestSchedulerStatus>('/admin/collector/digest/scheduler/status')
}

// 获取日报板块配置
export function getDigestSectionConfig(): Promise<{ sections: DigestSectionConfig[] }> {
  return get<{ sections: DigestSectionConfig[] }>('/admin/collector/digest/config/sections')
}

