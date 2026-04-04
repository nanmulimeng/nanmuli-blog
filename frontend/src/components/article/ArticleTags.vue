<script setup lang="ts">
import type { Tag } from '@/types/article'

defineProps<{
  tags: Tag[]
}>()

const emit = defineEmits<{
  click: [tag: Tag]
}>()

function handleClick(tag: Tag): void {
  emit('click', tag)
}
</script>

<template>
  <div class="flex flex-wrap gap-2">
    <span
      v-for="tag in tags"
      :key="tag.id"
      class="cursor-pointer rounded-full px-3 py-1 text-sm transition-colors hover:opacity-80"
      :style="{ backgroundColor: tag.color + '20', color: tag.color }"
      @click="handleClick(tag)"
    >
      {{ tag.name }}
    </span>
  </div>
</template>
