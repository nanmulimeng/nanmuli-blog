<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getPublicDigestByDate, getPublicLatestDigest } from '@/api/collector'
import type { DigestDetail } from '@/types/collector'
import { renderMarkdown } from '@/utils/markdown'
import { sanitize } from '@/utils/sanitize'
import { getDigestCategoryColor } from '@/constants/digest'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const digest = ref<DigestDetail | null>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const isLatest = computed(() => route.name === 'PublicDigestLatest')
const dateParam = computed(() => route.params.date as string)
const isInProgress = computed(() => digest.value !== null && digest.value.status !== 3 && digest.value.status !== 4)

function sectionBorderColor(category: string): string {
  return getDigestCategoryColor(category)
}

function stopPolling(): void {
  if (pollTimer !== null) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function schedulePoll(): void {
  stopPolling()
  if (isInProgress.value) {
    pollTimer = setTimeout(() => fetchDigest({ silent: true }), 5000)
  }
}

async function fetchDigest(options?: { silent?: boolean }): Promise<void> {
  if (!options?.silent) loading.value = true
  try {
    if (isLatest.value) {
      digest.value = await getPublicLatestDigest()
    } else {
      digest.value = await getPublicDigestByDate(dateParam.value)
    }
  } catch {
    digest.value = null
  } finally {
    loading.value = false
  }
  schedulePoll()
}

function goToList(): void {
  router.push('/digest')
}

onMounted(fetchDigest)

onUnmounted(stopPolling)

watch(dateParam, () => {
  fetchDigest()
})
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8">
    <div v-loading="loading">
      <template v-if="digest">
        <!-- In-progress banner -->
        <div v-if="isInProgress" class="mb-6 rounded-lg bg-primary/10 border border-primary/20 p-4 text-center text-sm text-primary">
          日报正在生成中，页面将自动刷新...
        </div>
        <!-- Header -->
        <div class="mb-8">
          <button
            class="mb-4 text-sm text-content-tertiary hover:text-primary transition-colors"
            @click="goToList"
          >
            &larr; 返回日报列表
          </button>
          <div class="flex items-center gap-3">
            <h1 class="text-3xl font-bold text-content-primary">
              {{ digest.digest_date || '技术日报' }}
            </h1>
          </div>
          <p v-if="digest.ai_summary" class="mt-4 text-base leading-relaxed text-content-secondary">
            {{ digest.ai_summary }}
          </p>
          <div v-if="digest.ai_tags?.length" class="mt-4 flex flex-wrap gap-2">
            <el-tag v-for="tag in digest.ai_tags" :key="tag" size="small" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
        </div>

        <!-- Highlight -->
        <div v-if="digest.highlight" class="mb-6 rounded-xl bg-primary/5 border border-primary/20 p-4">
          <div class="text-sm font-medium text-primary">今日亮点</div>
          <div class="mt-1 text-sm text-content-primary">{{ digest.highlight }}</div>
        </div>

        <!-- Structured Sections -->
        <div v-if="digest.sections?.length" class="space-y-6">
          <div
            v-for="section in digest.sections"
            :key="section.category"
            class="rounded-xl border-l-4 bg-surface-secondary p-5 shadow-sm"
            :style="{ borderLeftColor: sectionBorderColor(section.category) }"
          >
            <h2 class="mb-4 flex items-center gap-2 text-xl font-semibold text-content-primary">
              <span v-if="section.emoji">{{ section.emoji }}</span>
              {{ section.category_name }}
              <span class="text-sm font-normal text-content-tertiary">({{ section.items.length }})</span>
            </h2>

            <div v-if="section.items.length" class="space-y-3">
              <div
                v-for="(item, idx) in section.items"
                :key="idx"
                class="flex items-start gap-3 rounded-lg p-3 transition-colors hover:bg-surface-tertiary/50"
              >
                <span class="mt-0.5 flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-surface-tertiary text-xs font-medium text-content-secondary">
                  {{ idx + 1 }}
                </span>
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <a
                      v-if="item.source_url"
                      :href="item.source_url"
                      target="_blank"
                      rel="noopener"
                      class="text-sm font-medium text-content-primary hover:text-primary transition-colors"
                    >
                      {{ item.title }}
                    </a>
                    <span v-else class="text-sm font-medium text-content-primary">{{ item.title }}</span>
                    <span class="text-xs text-content-tertiary">{{ item.source_name }}</span>
                  </div>
                  <div v-if="item.one_liner" class="mt-1 text-sm text-content-secondary">
                    {{ item.one_liner }}
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="text-sm text-content-tertiary py-2">暂无内容</div>
          </div>
        </div>

        <!-- Full Content Fallback -->
        <div v-else-if="digest.ai_full_content" class="rounded-xl bg-surface-secondary p-6 shadow-sm">
          <div
            class="prose prose-sm max-w-none text-sm text-content-secondary dark:prose-invert"
            v-html="sanitize(renderMarkdown(digest.ai_full_content))"
          />
        </div>
      </template>

      <div v-if="!loading && !digest" class="py-20 text-center">
        <el-empty description="日报不存在" />
        <button class="mt-4 text-primary hover:underline" @click="goToList">返回日报列表</button>
      </div>
    </div>
  </div>
</template>
