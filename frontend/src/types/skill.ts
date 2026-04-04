export interface Skill {
  id: number
  name: string
  category: 'language' | 'framework' | 'tool' | 'other'
  proficiency: number
  icon: string
  color: string
  description: string
  sort: number
  status: number
  createTime: string
  updateTime: string
}
