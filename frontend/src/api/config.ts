import { get, put, post } from '@/utils/request'
import type { Config, ProxyStatus, ProxyGroup, NodeDelay } from '@/types/config'

export function getPublicConfig(): Promise<Record<string, string>> {
  return get<Record<string, string>>('/config/public')
}

export function updateConfig(key: string, value: string): Promise<void> {
  return put<void>(`/admin/config/${key}`, { value })
}

export function getAdminConfigList(): Promise<Config[]> {
  return get<Config[]>('/admin/config/list')
}

// ==================== 代理管理 ====================

export function getProxyStatus(): Promise<ProxyStatus> {
  return get<ProxyStatus>('/admin/proxy/status')
}

export function getProxyGroups(): Promise<ProxyGroup[]> {
  return get<ProxyGroup[]>('/admin/proxy/groups')
}

export function selectProxy(groupName: string, nodeName: string): Promise<void> {
  return put<void>(`/admin/proxy/groups/${encodeURIComponent(groupName)}`, {
    groupName,
    nodeName,
  })
}

export function testNodesDelay(groupName: string, nodeNames?: string[]): Promise<NodeDelay[]> {
  return post<NodeDelay[]>('/admin/proxy/nodes/delay-test', {
    groupName,
    nodeNames,
  })
}

export function getSubscriptionUrl(): Promise<string> {
  return get<string>('/admin/proxy/subscription')
}

export function updateSubscriptionUrl(url: string): Promise<void> {
  return put<void>('/admin/proxy/subscription', { url })
}

export function refreshSubscription(): Promise<void> {
  return post<void>('/admin/proxy/subscription/refresh')
}
