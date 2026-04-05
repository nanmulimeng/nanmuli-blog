// 注意：ID 使用 string 类型，因为 JavaScript number 无法精确表示 64 位整数
export interface Project {
  id: string
  name: string
  slug: string
  description: string
  cover: string
  screenshots: string[]
  techStack: string[]
  githubUrl: string
  demoUrl: string
  docUrl: string
  sort: number
  status: number
  startDate: string
  endDate: string
  createTime: string
  updateTime: string
}
