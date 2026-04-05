// 注意：ID 使用 string 类型，因为 JavaScript number 无法精确表示 64 位整数
export interface Tag {
  id: string
  name: string
  slug: string
  color: string
  icon: string
  description?: string
  articleCount: number
  status: number
  createTime: string
  updateTime: string
}
