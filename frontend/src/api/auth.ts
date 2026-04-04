import { post } from '@/utils/request'
import type { LoginForm, LoginResult } from '@/types/user'

export function login(data: LoginForm): Promise<LoginResult> {
  return post<LoginResult>('/auth/login', data)
}

export function logout(): Promise<void> {
  return post<void>('/auth/logout')
}

export function getCurrentUser(): Promise<LoginResult> {
  return post<LoginResult>('/auth/user')
}
