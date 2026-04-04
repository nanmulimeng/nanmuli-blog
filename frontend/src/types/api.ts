export interface Result<T> {
  code: number
  message: string
  data: T
  timestamp: number
}

export interface PageResult<T> {
  total: number
  current: number
  size: number
  records: T[]
}

export interface PageQuery {
  current?: number
  size?: number
}
