import { get, post, put, del } from '@/utils/request'
import type { Tag } from '@/types/tag'

export function getTagList(): Promise<Tag[]> {
  return get<Tag[]>('/tag/list')
}

export function getTagCloud(): Promise<Tag[]> {
  return get<Tag[]>('/tag/cloud')
}

export function createTag(data: Partial<Tag>): Promise<number> {
  return post<number>('/admin/tag', data)
}

export function updateTag(id: number, data: Partial<Tag>): Promise<void> {
  return put<void>(`/admin/tag/${id}`, data)
}

export function deleteTag(id: number): Promise<void> {
  return del<void>(`/admin/tag/${id}`)
}

export function getAdminTagList(): Promise<Tag[]> {
  return get<Tag[]>('/admin/tag/list')
}
