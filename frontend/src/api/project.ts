import { get, post, put, del } from '@/utils/request'
import type { Project } from '@/types/project'

export function getProjectList(): Promise<Project[]> {
  return get<Project[]>('/project/list')
}

export function createProject(data: Partial<Project>): Promise<number> {
  return post<number>('/admin/project', data)
}

export function updateProject(id: number, data: Partial<Project>): Promise<void> {
  return put<void>(`/admin/project/${id}`, data)
}

export function deleteProject(id: number): Promise<void> {
  return del<void>(`/admin/project/${id}`)
}
