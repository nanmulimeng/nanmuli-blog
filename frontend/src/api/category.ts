import { get, post, put, del } from '@/utils/request'
import type { Category, CategoryPageQuery, CategoryPageResult } from '@/types/category'

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

// 管理后台：分页查询分类列表
export function getCategoryPage(query: CategoryPageQuery): Promise<CategoryPageResult> {
  return get<CategoryPageResult>('/admin/category/page', { params: query })
}

// 获取分类详情
export function getCategoryById(id: string): Promise<Category> {
  return get<Category>(`/admin/category/${id}`)
}

// 获取分类路径
export function getCategoryPath(id: string): Promise<Category[]> {
  return get<Category[]>(`/admin/category/${id}/path`)
}

export function createCategory(data: Partial<Category>): Promise<string> {
  return post<string>('/admin/category', data)
}

export function updateCategory(id: string, data: Partial<Category>): Promise<void> {
  return put<void>(`/admin/category/${id}`, data)
}

export function deleteCategory(id: string): Promise<void> {
  return del<void>(`/admin/category/${id}`)
}
