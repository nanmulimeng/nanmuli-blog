import { post } from '@/utils/request'

export function uploadFile(file: File, usageType: string): Promise<{ url: string; fileName: string }> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('usageType', usageType)

  return post<{ url: string; fileName: string }>('/file/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}
