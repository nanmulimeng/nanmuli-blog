import { get } from '@/utils/request'

export function testAiConnection(): Promise<{
  configured: boolean
  available: boolean
  reason?: string
  provider?: string
  model?: string
  baseUrl?: string
  responsePreview?: string
}> {
  return get('/admin/ai/test')
}

export function getAiConfig(): Promise<{
  enabled: boolean
  provider: string
  model: string
  baseUrl: string
  temperature: number
  configured: boolean
  apiKeyMasked: string
}> {
  return get('/admin/ai/config')
}
