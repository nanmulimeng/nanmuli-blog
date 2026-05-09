/**
 * 心情（Mood）相关常量
 */

export interface MoodOption {
  icon: string
  label: string
  color: string
  bgColor: string
  description: string
}

export const MOOD_MAP: Record<string, MoodOption> = {
  happy: { icon: 'Sunny', label: '开心', color: '#f59e0b', bgColor: '#fef3c7', description: '充满能量，效率很高' },
  excited: { icon: 'Star', label: '兴奋', color: '#ef4444', bgColor: '#fee2e2', description: '充满激情，学习热情高涨' },
  normal: { icon: 'Minus', label: '平静', color: '#64748B', bgColor: '#f1f5f9', description: '稳步推进，保持节奏' },
  tired: { icon: 'Moon', label: '疲惫', color: '#3B82F6', bgColor: '#dbeafe', description: '需要休息，适当放松' },
}

/** 默认心情颜色（未匹配时使用） */
export const MOOD_DEFAULT_COLOR = '#64748B'

/** 默认心情图标 */
export const MOOD_DEFAULT_ICON = 'Minus'

/** 默认心情标签 */
export const MOOD_DEFAULT_LABEL = '平静'
