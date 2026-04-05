// 注意：ID 使用 string 类型，因为 JavaScript number 无法精确表示 64 位整数
export interface Config {
  id: string
  configKey: string
  configValue: string
  defaultValue: string
  description: string
  groupName: string
  isPublic: boolean
  sensitive?: boolean
}
