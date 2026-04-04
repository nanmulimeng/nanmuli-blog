export interface Category {
  id: number
  name: string
  slug: string
  description: string
  icon: string
  color: string
  sort: number
  parentId: number
  articleCount: number
  status: number
  createTime: string
  updateTime: string
}
