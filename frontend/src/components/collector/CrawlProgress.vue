<script setup lang="ts">
defineProps<{
  percent: number
  completed: number
  total: number
  status: number
}>()
</script>

<template>
  <div class="flex items-center gap-2">
    <el-progress
      :percentage="percent"
      :stroke-width="8"
      :show-text="false"
      :color="status === 4 ? '#EF4444' : undefined"
      class="flex-1"
    />
    <span class="text-xs text-content-tertiary whitespace-nowrap">
      {{ completed }}/{{ total }}
    </span>
  </div>
</template>
