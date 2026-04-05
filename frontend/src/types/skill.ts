// 注意：ID 使用 string 类型，因为 JavaScript number 无法精确表示 64 位整数
export interface Skill {
  id: string
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
