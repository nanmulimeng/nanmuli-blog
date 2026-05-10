<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  title?: string
  icon?: string
  size?: 'sm' | 'md' | 'lg'
}>(), {
  size: 'md',
})

const gradients = [
  ['#667eea', '#764ba2'],
  ['#4facfe', '#00f2fe'],
  ['#43e97b', '#38f9d7'],
  ['#fa709a', '#fee140'],
  ['#a18cd1', '#fbc2eb'],
  ['#fccb90', '#d57eeb'],
  ['#e0c3fc', '#8ec5fc'],
  ['#f5576c', '#ff9a44'],
  ['#3b82f6', '#06b6d4'],
  ['#6366f1', '#8b5cf6'],
]

const charCode = computed(() => {
  let hash = 0
  const seed = props.title || 'default'
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash)
    hash = hash & hash
  }
  return Math.abs(hash)
})

const gradient = computed(() => gradients[charCode.value % gradients.length]!)

const displayChar = computed(() => (props.title || '?')[0]!.toUpperCase())

const iconSize = computed(() => props.size === 'sm' ? 28 : props.size === 'lg' ? 64 : 40)

</script>

<template>
  <div class="cover-placeholder">
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 800 450"
      preserveAspectRatio="xMidYMid slice"
      class="cover-placeholder-svg"
    >
      <defs>
        <linearGradient :id="`bg-${charCode}`" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" :style="{ stopColor: gradient[0] }" />
          <stop offset="100%" :style="{ stopColor: gradient[1] }" />
        </linearGradient>
        <linearGradient :id="`circle-${charCode}`" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" :style="{ stopColor: gradient[0], stopOpacity: 0.25 }" />
          <stop offset="100%" :style="{ stopColor: gradient[1], stopOpacity: 0.15 }" />
        </linearGradient>
        <pattern :id="`dots-${charCode}`" width="40" height="40" patternUnits="userSpaceOnUse">
          <circle cx="20" cy="20" r="1.5" fill="white" opacity="0.08" />
        </pattern>
      </defs>

      <!-- Background -->
      <rect width="800" height="450" :fill="`url(#bg-${charCode})`" />

      <!-- Dot pattern overlay -->
      <rect width="800" height="450" :fill="`url(#dots-${charCode})`" />

      <!-- Decorative circles -->
      <circle cx="680" cy="80" r="180" :fill="`url(#circle-${charCode})`" />
      <circle cx="120" cy="370" r="120" :fill="`url(#circle-${charCode})`" />
      <circle cx="720" cy="400" r="80" :fill="`url(#circle-${charCode})`" />

      <!-- Center icon circle -->
      <circle cx="400" cy="200" r="45" fill="white" opacity="0.18" />
      <circle cx="400" cy="200" r="38" fill="white" opacity="0.12" />

      <!-- Icon -->
      <text
        x="400"
        y="212"
        text-anchor="middle"
        fill="white"
        font-family="system-ui, sans-serif"
        :font-size="iconSize"
        font-weight="700"
        opacity="0.9"
      >
        {{ displayChar }}
      </text>

      <!-- Decorative lines -->
      <line x1="280" y1="110" x2="350" y2="110" stroke="white" stroke-opacity="0.12" stroke-width="2" />
      <line x1="450" y1="110" x2="520" y2="110" stroke="white" stroke-opacity="0.12" stroke-width="2" />
      <line x1="280" y1="295" x2="350" y2="295" stroke="white" stroke-opacity="0.12" stroke-width="2" />
      <line x1="450" y1="295" x2="520" y2="295" stroke="white" stroke-opacity="0.12" stroke-width="2" />
    </svg>
  </div>
</template>

<style scoped>
.cover-placeholder {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: var(--surface-tertiary, #f0f0f0);
}

.cover-placeholder-svg {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
