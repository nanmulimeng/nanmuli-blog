import { post, get } from '@/utils/request'
import type { AxiosRequestConfig } from 'axios'
import type { LoginForm, UserInfo } from '@/types/user'

export function login(data: LoginForm): Promise<string> {
  return post<string>('/auth/login', data)
}

export function logout(): Promise<void> {
  return post<void>('/auth/logout')
}

export function getCurrentUser(config?: AxiosRequestConfig): Promise<UserInfo> {
  return get<UserInfo>('/auth/info', config)
}
