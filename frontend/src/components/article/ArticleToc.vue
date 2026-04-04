<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface TocItem {
  id: string
  text: string
  level: number
}

const tocList = ref<TocItem[]>([])

function generateToc(): void {
  const headings = document.querySelectorAll('.markdown-body h2, .markdown-body h3')
  tocList.value = Array.from(headings).map((heading, index) => {
    const id = `heading-${index}`
    heading.id = id
    return {
      id,
      text: heading.textContent || '',
      level: heading.tagName === 'H2' ? 2 : 3,
    }
  })
}

function scrollToHeading(id: string): void {
  const element = document.getElementById(id)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth' })
  }
}

onMounted(generateToc)
</script>

<template>
  <div v-if="tocList.length > 0" class="rounded-xl border bg-white p-4">
    <h4 class="mb-4 font-semibold text-gray-900">目录</h4>
    <nav class="space-y-2">
      <a
        v-for="item in tocList"
        :key="item.id"
        class="block cursor-pointer text-sm transition-colors hover:text-blue-600"
        :class="item.level === 2 ? 'text-gray-700' : 'pl-4 text-gray-500'"
        @click="scrollToHeading(item.id)"
      >
        {{ item.text }}
      </a>
    </nav>
  </div>
</template>
