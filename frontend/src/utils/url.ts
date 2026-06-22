const SAFE_EXTERNAL_PROTOCOLS = new Set(['http:', 'https:'])
const MAX_EXTERNAL_URL_LENGTH = 2048

export function safeExternalUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined
  const trimmed = url.trim()
  if (!trimmed || trimmed.length > MAX_EXTERNAL_URL_LENGTH) return undefined

  try {
    const parsed = new URL(trimmed)
    if (!SAFE_EXTERNAL_PROTOCOLS.has(parsed.protocol)) return undefined
    return parsed.toString()
  } catch {
    return undefined
  }
}

export function isSafeExternalUrl(url: string | null | undefined): boolean {
  return safeExternalUrl(url) !== undefined
}

export function openSafeExternalUrl(
  url: string | null | undefined,
  target = '_blank',
  features = 'noopener,noreferrer',
): void {
  const safeUrl = safeExternalUrl(url)
  if (!safeUrl) return
  window.open(safeUrl, target, features)
}
