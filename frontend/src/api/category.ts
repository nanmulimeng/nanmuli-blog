import { get, post, put, del } from '@/utils/request'
import type { Category } from '@/types/category'

export function getCategoryList(): Promise<Category[]> {
  return get<Category[]>('/category/list')
}

export function createCategory(data: Partial<Category>): Promise<number> {
  return post<number>('/admin/category', data)
}

export function updateCategory(id: number, data: Partial<Category>): Promise<void> {
  return put<void>(`/admin/category/${id}`, data)
}

export function deleteCategory(id: number): Promise<void> {
  return del<void>(`/admin/category/${id}`)
}
