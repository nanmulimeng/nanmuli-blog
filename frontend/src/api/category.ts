import { get, post, put, del } from '@/utils/request'
import type { Category } from '@/types/category'

// 获取分类树（包含层级结构）
export function getCategoryList(): Promise<Category[]> {
  return get<Category[]>('/category/list')
}

// 获取叶子分类列表（可关联文章的分类）
export function getLeafCategoryList(): Promise<Category[]> {
  return get<Category[]>('/category/leaf')
}

// 管理后台：获取完整分类树
export function getAdminCategoryList(): Promise<Category[]> {
  return get<Category[]>('/admin/category/list')
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
