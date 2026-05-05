/**
 * 生成或获取访客ID
 * 用于统计独立访客(UV)
 */
export function generateVisitorId(): string {
  const storageKey = 'blog_visitor_id'

  // 尝试从 localStorage 获取已有的 visitorId
  let visitorId = localStorage.getItem(storageKey)

  if (!visitorId) {
    // 生成新的 visitorId (使用随机字符串 + 时间戳)
    const randomStr = Math.random().toString(36).substring(2, 15)
    const timestamp = Date.now().toString(36)
    visitorId = `${randomStr}${timestamp}`

    // 存储到 localStorage
    localStorage.setItem(storageKey, visitorId)
  }

  return visitorId
}

