import { get, post, put, del } from '@/utils/request'
import type { FriendLink } from '@/types/friendLink'

export function getFriendLinkList(): Promise<FriendLink[]> {
  return get<FriendLink[]>('/friend-link/list')
}

export function getAdminFriendLinkList(): Promise<FriendLink[]> {
  return get<FriendLink[]>('/admin/friend-link/list')
}

export function createFriendLink(data: Partial<FriendLink>): Promise<string> {
  return post<string>('/admin/friend-link', data)
}

export function updateFriendLink(id: string, data: Partial<FriendLink>): Promise<void> {
  return put<void>(`/admin/friend-link/${id}`, data)
}

export function deleteFriendLink(id: string): Promise<void> {
  return del<void>(`/admin/friend-link/${id}`)
}
