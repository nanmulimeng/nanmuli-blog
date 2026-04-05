export interface Category {
  id: number
  name: string
  slug: string
  description: string
  icon: string
  color: string
  sort: number
  parentId: number | null
  articleCount: number
  status: number
  isLeaf: boolean
  createTime: string
  updateTime: string
  children?: Category[]
}
