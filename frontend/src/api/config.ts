import { get, put } from '@/utils/request'
import type { Config } from '@/types/config'

export function getPublicConfig(): Promise<Record<string, string>> {
  return get<Record<string, string>>('/config/public')
}

export function updateConfig(key: string, value: string): Promise<void> {
  return put<void>(`/admin/config/${key}`, { value })
}

export function getAdminConfigList(): Promise<Config[]> {
  return get<Config[]>('/admin/config/list')
}
