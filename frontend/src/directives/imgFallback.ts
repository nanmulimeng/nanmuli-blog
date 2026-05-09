import type { Directive } from 'vue'

// 默认占位 SVG — 灰色背景 + 图片图标
const FALLBACK_SRC = `data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" fill="none">'
  + '<rect width="400" height="300" fill="#f0f0f0"/>'
  + '<text x="200" y="155" text-anchor="middle" fill="#999" font-size="16" font-family="sans-serif">图片加载失败</text>'
  + '</svg>',
)}`

/**
 * v-img-fallback 指令 — 图片加载失败时显示占位图
 *
 * 用法：
 *   <img :src="url" v-img-fallback />
 *   <img :src="url" v-img-fallback="/path/to/custom-fallback.png" />
 */
export const imgFallback: Directive<HTMLImageElement, string | undefined> = {
  mounted(el, binding) {
    const fallback = binding.value || FALLBACK_SRC
    el.addEventListener('error', function handler() {
      // 防止无限循环（fallback 本身也失败）
      el.removeEventListener('error', handler)
      if (el.src !== fallback) {
        el.src = fallback
      }
    })
  },
}
