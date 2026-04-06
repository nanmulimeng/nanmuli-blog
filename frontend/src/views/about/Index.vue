<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfigStore } from '@/stores/modules/config'
import { getSkillList } from '@/api/skill'
import type { Skill } from '@/types/skill'

const configStore = useConfigStore()
const skills = ref<Skill[]>([])
const loading = ref(false)

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
          <div class="w-28 h-28 md:w-32 md:h-32 rounded-full overflow-hidden border-4 border-surface-secondary shadow-lg bg-primary-100 flex items-center justify-center">
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
        <h1 class="mt-6 text-2xl md:text-3xl font-bold text-content-primary">
          {{ configStore.siteAuthor || '博主' }}
        </h1>
        <p class="mt-2 text-content-secondary">全栈开发工程师 | 技术博主</p>

        <!-- Social Links -->
        <div class="mt-6 flex justify-center gap-4">
          <a
            v-if="configStore.siteGithub"
            :href="configStore.siteGithub"
            target="_blank"
            rel="noopener noreferrer"
            class="w-10 h-10 rounded-full bg-surface-tertiary flex items-center justify-center text-content-secondary hover:bg-surface-tertiary hover:text-content-primary transition-colors"
            aria-label="GitHub"
          >
            <el-icon><Promotion /></el-icon>
          </a>
          <a
            v-if="configStore.siteEmail"
            :href="`mailto:${configStore.siteEmail}`"
            class="w-10 h-10 rounded-full bg-surface-tertiary flex items-center justify-center text-content-secondary hover:bg-surface-tertiary hover:text-content-primary transition-colors"
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
        <h2 class="text-xl font-bold text-content-primary mb-6">关于我</h2>
        <div class="prose prose-gray max-w-none text-content-secondary leading-relaxed" v-html="configStore.siteAbout" />
      </div>
    </section>

    <!-- Skills Section -->
    <section class="py-12">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-xl font-bold text-content-primary mb-8">技能栈</h2>

        <div class="space-y-8">
          <div v-for="cat in skillCategories" :key="cat.key">
            <h3 class="text-sm font-medium text-content-tertiary uppercase tracking-wide mb-4">{{ cat.name }}</h3>

            <div class="grid gap-3 sm:grid-cols-2">
              <div
                v-for="skill in skills.filter(s => s.category === cat.key)"
                :key="skill.id"
                class="flex items-center gap-3 bg-surface-primary rounded-lg p-3 border border-border"
              >
                <img v-if="skill.icon" :src="skill.icon" class="w-6 h-6" :alt="skill.name">
                <span class="flex-1 font-medium text-content-primary">{{ skill.name }}</span>

                <div class="flex gap-1">
                  <div
                    v-for="i in 5"
                    :key="i"
                    class="w-2 h-2 rounded-full"
                    :class="i <= skill.proficiency ? 'bg-primary' : 'bg-surface-secondary'"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Focus Areas -->
    <section class="py-12">
      <div class="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <h2 class="text-xl font-bold text-content-primary mb-8">专注领域</h2>
        <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div class="bg-surface-primary rounded-xl p-5 border border-border hover:border-primary transition-colors">
            <div class="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-3">
              <el-icon class="text-primary"><Monitor /></el-icon>
            </div>
            <h3 class="font-semibold text-content-primary mb-1">后端开发</h3>
            <p class="text-sm text-content-secondary">Java / Spring Boot / 分布式系统</p>
          </div>
          <div class="bg-surface-primary rounded-xl p-5 border border-border hover:border-primary transition-colors">
            <div class="w-10 h-10 rounded-lg bg-success/10 flex items-center justify-center mb-3">
              <el-icon class="text-success"><Collection /></el-icon>
            </div>
            <h3 class="font-semibold text-content-primary mb-1">前端开发</h3>
            <p class="text-sm text-content-secondary">Vue.js / TypeScript / 现代前端工程化</p>
          </div>
          <div class="bg-surface-primary rounded-xl p-5 border border-border hover:border-primary transition-colors">
            <div class="w-10 h-10 rounded-lg bg-warning/10 flex items-center justify-center mb-3">
              <el-icon class="text-warning"><DataLine /></el-icon>
            </div>
            <h3 class="font-semibold text-content-primary mb-1">数据库</h3>
            <p class="text-sm text-content-secondary">PostgreSQL / MySQL / Redis</p>
          </div>
          <div class="bg-surface-primary rounded-xl p-5 border border-border hover:border-primary transition-colors">
            <div class="w-10 h-10 rounded-lg bg-info/10 flex items-center justify-center mb-3">
              <el-icon class="text-info"><Ship /></el-icon>
            </div>
            <h3 class="font-semibold text-content-primary mb-1">DevOps</h3>
            <p class="text-sm text-content-secondary">Docker / CI/CD / 云原生部署</p>
          </div>
          <div class="bg-surface-primary rounded-xl p-5 border border-border hover:border-primary transition-colors">
            <div class="w-10 h-10 rounded-lg bg-purple/10 flex items-center justify-center mb-3">
              <el-icon class="text-purple"><Cpu /></el-icon>
            </div>
            <h3 class="font-semibold text-content-primary mb-1">人工智能</h3>
            <p class="text-sm text-content-secondary">LLM应用 / AI工程化 / 智能助手</p>
          </div>
          <div class="bg-surface-primary rounded-xl p-5 border border-border hover:border-primary transition-colors">
            <div class="w-10 h-10 rounded-lg bg-danger/10 flex items-center justify-center mb-3">
              <el-icon class="text-danger"><Lock /></el-icon>
            </div>
            <h3 class="font-semibold text-content-primary mb-1">安全技术</h3>
            <p class="text-sm text-content-secondary">安全研究 / 代码审计 / 漏洞分析</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
