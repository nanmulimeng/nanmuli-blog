<script setup lang="ts">
import { ref, computed } from 'vue'

const props = withDefaults(defineProps<{
  src: string
  alt?: string
  width?: number
  height?: number
  aspectRatio?: string
  webp?: string
  lazy?: boolean
  defer?: boolean
  fit?: 'cover' | 'contain' | 'fill' | 'none'
  lightbox?: boolean
  fallbackIcon?: boolean
}>(), {
  lazy: true,
  defer: true,
  fit: 'cover',
})

const imgRef = ref<HTMLImageElement>()
const resolved = ref(false)
const error = ref(false)
const lightboxVisible = ref(false)

const aspectStyle = computed(() => {
  if (props.aspectRatio) {
    return { aspectRatio: props.aspectRatio }
  }
  if (props.width && props.height) {
    return { aspectRatio: `${props.width} / ${props.height}` }
  }
  return {}
})

function onLoad() {
  resolved.value = true
}

function onError() {
  resolved.value = true
  error.value = true
}

function onClick() {
  if (props.lightbox) {
    lightboxVisible.value = true
  }
}

function closeLightbox() {
  lightboxVisible.value = false
}

defineExpose({ imgRef })
</script>

<template>
  <div
    class="src-image-container"
    :class="{ 'src-image-loaded': resolved }"
    :style="aspectStyle"
  >
    <!-- 骨架屏 -->
    <div v-if="!resolved" class="src-image-skeleton skeleton-loading" />

    <!-- WebP 版 -->
    <picture v-if="webp">
      <source :srcset="webp" type="image/webp" />
      <img
        ref="imgRef"
        :src="src"
        :alt="alt"
        :width="width"
        :height="height"
        :loading="lazy ? 'lazy' : 'eager'"
        :decoding="defer ? 'async' : 'auto'"
        :class="['src-image-img', `src-image-fit-${fit}`]"
        @load="onLoad"
        @error="onError"
        @click="onClick"
      />
    </picture>

    <!-- 标准 img -->
    <img
      v-else
      ref="imgRef"
      :src="src"
      :alt="alt"
      :width="width"
      :height="height"
      :loading="lazy ? 'lazy' : 'eager'"
      :decoding="defer ? 'async' : 'auto'"
      :class="['src-image-img', `src-image-fit-${fit}`]"
      @load="onLoad"
      @error="onError"
      @click="onClick"
    />

    <!-- 错误兜底 -->
    <div v-if="error" class="src-image-fallback">
      <slot name="fallback">
        <svg class="src-image-fallback-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="2" y="2" width="20" height="20" rx="3" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path d="M22 15l-5-5L3 21" />
        </svg>
      </slot>
    </div>
  </div>

  <!-- Lightbox -->
  <Teleport v-if="lightboxVisible" to="body">
    <div class="src-image-lightbox" @click="closeLightbox">
      <img :src="src" class="src-image-lightbox-img" :alt="alt" />
    </div>
  </Teleport>
</template>

<style scoped>
.src-image-container {
  position: relative;
  overflow: hidden;
  background: var(--surface-tertiary, #f0f0f0);
}

.src-image-skeleton {
  position: absolute;
  inset: 0;
  z-index: 1;
}

.src-image-loaded .src-image-skeleton {
  display: none;
}

.src-image-img {
  width: 100%;
  height: 100%;
  opacity: 0;
  transition: opacity 0.4s ease;
}

.src-image-loaded .src-image-img {
  opacity: 1;
}

.src-image-fit-cover { object-fit: cover; }
.src-image-fit-contain { object-fit: contain; }
.src-image-fit-fill { object-fit: fill; }
.src-image-fit-none { object-fit: none; }

.src-image-fallback {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-tertiary, #f0f0f0);
}

.src-image-fallback-icon {
  width: 32px;
  height: 32px;
  color: var(--content-tertiary, #999);
}

.src-image-lightbox {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
}

.src-image-lightbox-img {
  max-width: 90vw;
  max-height: 90vh;
  object-fit: contain;
}
</style>
