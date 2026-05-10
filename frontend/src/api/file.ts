import { get, post, del } from '@/utils/request'
import type { PageResult } from '@/types/api'

export interface FileDTO {
  id: string
  originalName: string
  fileUrl: string
  thumbnailUrl?: string
  width?: number
  height?: number
  fileSize: number
  mimeType: string
  storageType: string
  createTime: string
}

export interface FilePageParams {
  current: number
  size: number
  keyword?: string
  fileType?: string
}

export function uploadFile(formData: FormData): Promise<FileDTO> {
  return post<FileDTO>('/admin/file/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getFileList(params: FilePageParams): Promise<PageResult<FileDTO>> {
  return get<PageResult<FileDTO>>('/admin/file/list', { params })
}

export function deleteFile(id: string): Promise<void> {
  return del<void>(`/admin/file/${id}`)
}
