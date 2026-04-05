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

// 分类分页查询参数
export interface CategoryPageQuery {
  current?: number
  size?: number
  parentId?: number | null
  isLeaf?: boolean | null
  status?: number | null
  keyword?: string
}

// 分类分页结果
export interface CategoryPageResult {
  total: number
  current: number
  size: number
  records: Category[]
}
