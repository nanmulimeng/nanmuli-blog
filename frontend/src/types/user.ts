export interface LoginForm {
  username: string
  password: string
}

// 注意：ID 使用 string 类型，因为 JavaScript number 无法精确表示 64 位整数
export interface UserInfo {
  id: string
  username: string
  nickname: string
  avatar: string
  email: string
  role: string
}
