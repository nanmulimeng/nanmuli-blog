import { get, post, put, del } from '@/utils/request'
import type { Skill } from '@/types/skill'

export function getSkillList(): Promise<Skill[]> {
  return get<Skill[]>('/skill/list')
}

export function getAdminSkillList(): Promise<Skill[]> {
  return get<Skill[]>('/admin/skill/list')
}

export function createSkill(data: Partial<Skill>): Promise<string> {
  return post<string>('/admin/skill', data)
}

export function updateSkill(id: string, data: Partial<Skill>): Promise<void> {
  return put<void>(`/admin/skill/${id}`, data)
}

export function deleteSkill(id: string): Promise<void> {
  return del<void>(`/admin/skill/${id}`)
}

