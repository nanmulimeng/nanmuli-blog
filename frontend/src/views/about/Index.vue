<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfigStore } from '@/stores/modules/config'
import { getSkillList } from '@/api/skill'
import type { Skill } from '@/types/skill'

const configStore = useConfigStore()
const skills = ref<Skill[]>([])
const loading = ref(false)

const experiences = [
  {
    period: '2024年 - 至今',
    title: '高级开发工程师',
    company: 'XXX科技有限公司',
    description: '负责核心业务系统架构设计与开发'
  },
  {
    period: '2022年 - 2024年',
    title: '中级开发工程师',
    company: 'YYY互联网公司',
    description: '参与电商平台后端开发'
  },
  {
    period: '2020年 - 2022年',
    title: '计算机科学硕士',
    company: 'ZZZ大学',
    description: '研究方向：分布式系统'
  }
]

const skillCategories = [
  { key: 'language', name: '编程语言' },
  { key: 'framework', name: '框架' },
  { key: 'tool', name: '工具' },
  { key: 'other', name: '其他' }
]

async function fetchSkills(): Promise<void> {
  loading.value = true
  try {
    const res = await getSkillList()
    skills.value = res
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchSkills()
  configStore.loadConfig()
})
</script>

<template>
  <div class="about-page">
    <!-- Profile Section -->
    <section class="pt-24 pb-12">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 text-center">
        <!-- Avatar -->
        <div class="relative inline-block">
          <div class="w-28 h-28 md:w-32 md:h-32 rounded-full overflow-hidden border-4 border-white shadow-lg bg-primary-100 flex items-center justify-center">
            <img
              v-if="configStore.siteAvatar"
              :src="configStore.siteAvatar"
              alt="Avatar"
              class="w-full h-full object-cover"
            >
            <el-icon v-else :size="48" class="text-primary-600"><UserFilled /></el-icon>
          </div>
        </div>

        <!-- Name & Title -->
        <h1 class="mt-6 text-2xl md:text-3xl font-bold text-gray-900">
          {{ configStore.siteAuthor || '博主' }}
        </h1>
        <p class="mt-2 text-gray-500">全栈开发工程师 | 技术博主</p>

        <!-- Social Links -->
        <div class="mt-6 flex justify-center gap-4">
          <a
            v-if="configStore.siteGithub"
            :href="configStore.siteGithub"
            target="_blank"
            rel="noopener noreferrer"
            class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-600 hover:bg-gray-200 hover:text-gray-900 transition-colors"
            aria-label="GitHub"
          >
            <el-icon><Promotion /></el-icon>
          </a>
          <a
            v-if="configStore.siteEmail"
            :href="`mailto:${configStore.siteEmail}`"
            class="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-600 hover:bg-gray-200 hover:text-gray-900 transition-colors"
            aria-label="邮箱"
          >
            <el-icon><Message /></el-icon>
          </a>
        </div>
      </div>
    </section>

    <!-- Bio Section -->
    <section v-if="configStore.siteAbout" class="py-12">
      <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-xl font-bold text-gray-900 mb-6">关于我</h2>
        <div class="prose prose-gray max-w-none text-gray-600 leading-relaxed" v-html="configStore.siteAbout" />
      </div>
    </section>

    <!-- Skills Section -->
    <section class="py-12 bg-gray-50">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-xl font-bold text-gray-900 mb-8">技能栈</h2>

        <div class="space-y-8">
          <div v-for="cat in skillCategories" :key="cat.key">
            <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">{{ cat.name }}</h3>

            <div class="grid gap-3 sm:grid-cols-2">
              <div
                v-for="skill in skills.filter(s => s.category === cat.key)"
                :key="skill.id"
                class="flex items-center gap-3 bg-white rounded-lg p-3"
              >
                <img v-if="skill.icon" :src="skill.icon" class="w-6 h-6" :alt="skill.name">
                <span class="flex-1 font-medium text-gray-900">{{ skill.name }}</span>

                <div class="flex gap-1">
                  <div
                    v-for="i in 5"
                    :key="i"
                    class="w-2 h-2 rounded-full"
                    :class="i <= skill.proficiency ? 'bg-primary-500' : 'bg-gray-200'"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Experience Timeline -->
    <section class="py-12">
      <div class="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-xl font-bold text-gray-900 mb-8">经历</h2>

        <div class="relative border-l-2 border-gray-200 ml-3 space-y-8">
          <div v-for="(exp, index) in experiences" :key="index" class="relative pl-8">
            <div class="absolute -left-2 top-1 w-4 h-4 rounded-full bg-primary-500 border-2 border-white" />

            <div class="text-sm text-primary-600 font-medium">{{ exp.period }}</div>
            <h3 class="mt-1 text-lg font-semibold text-gray-900">{{ exp.title }}</h3>
            <div class="text-gray-500">{{ exp.company }}</div>
            <p class="mt-2 text-gray-600">{{ exp.description }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
