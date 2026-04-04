export function getItem<T>(key: string): T | null {
  try {
    const item = localStorage.getItem(key)
    return item ? (JSON.parse(item) as T) : null
  } catch {
    return null
  }
}

export function setItem(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // 忽略写入错误
  }
}

export function removeItem(key: string): void {
  localStorage.removeItem(key)
}

export function clear(): void {
  localStorage.clear()
}
