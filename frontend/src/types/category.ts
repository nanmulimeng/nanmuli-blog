// 注意：ID 使用 string 类型，因为 JavaScript number 无法精确表示 64 位整数
export interface Category {
  id: string
  name: string
  slug: string
  description: string
  icon: string
  color: string
  sort: number
  parentId: string | null
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
  parentId?: string | null
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
