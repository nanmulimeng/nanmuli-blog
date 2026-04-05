import { get, post, put, del } from '@/utils/request'
import type { Project } from '@/types/project'

export function getProjectList(): Promise<Project[]> {
  return get<Project[]>('/project/list')
}

export function createProject(data: Partial<Project>): Promise<string> {
  return post<string>('/admin/project', data)
}

export function updateProject(id: string, data: Partial<Project>): Promise<void> {
  return put<void>(`/admin/project/${id}`, data)
}

export function deleteProject(id: string): Promise<void> {
  return del<void>(`/admin/project/${id}`)
}

export function getProjectById(id: string): Promise<Project> {
  return get<Project>(`/project/${id}`)
}
