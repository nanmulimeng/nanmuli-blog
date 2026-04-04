import { get, post, put, del } from '@/utils/request'
import type { Skill } from '@/types/skill'

export function getSkillList(): Promise<Skill[]> {
  return get<Skill[]>('/skill/list')
}

export function createSkill(data: Partial<Skill>): Promise<number> {
  return post<number>('/admin/skill', data)
}

export function updateSkill(id: number, data: Partial<Skill>): Promise<void> {
  return put<void>(`/admin/skill/${id}`, data)
}

export function deleteSkill(id: number): Promise<void> {
  return del<void>(`/admin/skill/${id}`)
}
