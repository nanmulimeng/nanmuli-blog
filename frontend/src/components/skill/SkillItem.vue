<script setup lang="ts">
import type { Skill } from '@/types/skill'

defineProps<{
  skill: Skill
}>()
</script>
<script lang="ts">
export default {
  name: 'SkillItem'
}
</script>

<template>
  <div class="flex items-center gap-4 rounded-lg border border-border bg-surface-secondary p-4">
    <div
      v-if="skill.icon"
      class="flex h-12 w-12 items-center justify-center rounded-lg"
      :style="{ backgroundColor: skill.color + '20' }"
    >
      <img :src="skill.icon" :alt="skill.name" class="h-8 w-8" />
    </div>
    <div v-else class="flex h-12 w-12 items-center justify-center rounded-lg bg-surface-tertiary">
      <span class="text-xl text-content-primary">{{ skill.name.charAt(0) }}</span>
    </div>

    <div class="flex-1">
      <div class="mb-1 flex items-center justify-between">
        <span class="font-medium text-content-primary">{{ skill.name }}</span>
        <span class="text-sm text-content-tertiary">{{ skill.proficiency }}/5</span>
      </div>

      <div class="h-2 overflow-hidden rounded-full bg-surface-tertiary">
        <div
          class="h-full rounded-full transition-all duration-500"
          :style="{
            width: `${(skill.proficiency / 5) * 100}%`,
            backgroundColor: skill.color || '#3b82f6',
          }"
        />
      </div>

      <p v-if="skill.description" class="mt-1 text-xs text-content-tertiary">
        {{ skill.description }}
      </p>
    </div>
  </div>
</template>
