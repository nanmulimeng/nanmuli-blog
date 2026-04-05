<script setup lang="ts">
defineProps<{
  html: string
}>()
</script>

<template>
  <div class="markdown-body prose prose-slate max-w-none" v-html="html" />
</template>

<style scoped>
:deep(.markdown-body) {
  @apply text-content-primary leading-relaxed;
}

:deep(.markdown-body h1) {
  @apply text-3xl font-bold mb-6 pb-4 border-b;
}

:deep(.markdown-body h2) {
  @apply text-2xl font-bold mt-8 mb-4;
}

:deep(.markdown-body h3) {
  @apply text-xl font-bold mt-6 mb-3;
}

:deep(.markdown-body p) {
  @apply mb-4;
}

:deep(.markdown-body pre) {
  @apply bg-surface-secondary text-content-primary p-4 rounded-lg overflow-x-auto mb-4;
  background-color: #1e1e2e;
  color: #cdd6f4;
}

:deep(.markdown-body code) {
  @apply font-mono text-sm;
}

:deep(.markdown-body :not(pre) > code) {
  @apply bg-surface-tertiary text-primary px-1.5 py-0.5 rounded text-sm;
}

:deep(.markdown-body ul),
:deep(.markdown-body ol) {
  @apply mb-4 pl-6;
}

:deep(.markdown-body ul) {
  @apply list-disc;
}

:deep(.markdown-body ol) {
  @apply list-decimal;
}

:deep(.markdown-body blockquote) {
  @apply border-l-4 border-primary pl-4 italic text-content-secondary my-4;
}

:deep(.markdown-body img) {
  @apply max-w-full rounded-lg;
}

:deep(.markdown-body a) {
  @apply text-blue-600 hover:underline;
}

:deep(.markdown-body table) {
  @apply w-full border-collapse mb-4;
}

:deep(.markdown-body th),
:deep(.markdown-body td) {
  @apply border border-border px-4 py-2;
}

:deep(.markdown-body th) {
  @apply bg-surface-tertiary font-semibold;
}
</style>
