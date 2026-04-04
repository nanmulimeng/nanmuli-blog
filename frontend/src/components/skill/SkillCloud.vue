<script setup lang="ts">
import type { Skill } from '@/types/skill'

const props = defineProps<{
  skills: Skill[]
}>()

// 按分类分组技能
const groupedSkills = computed(() => {
  const groups: Record<string, Skill[]> = {}
  props.skills.forEach((skill) => {
    const category = skill.category || 'other'
    if (!groups[category]) {
      groups[category] = []
    }
    groups[category].push(skill)
  })
  return groups
})

const categoryLabels: Record<string, string> = {
  language: '编程语言',
  framework: '框架',
  tool: '工具',
  other: '其他',
}
</script>

<template>
  <div class="space-y-8">
    <div v-for="(skills, category) in groupedSkills" :key="category">
      <h4 class="mb-4 text-lg font-semibold text-gray-900">
        {{ categoryLabels[category] || category }}
      </h4>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <SkillItem v-for="skill in skills" :key="skill.id" :skill="skill" />
      </div>
    </div>
  </div>
</template>
