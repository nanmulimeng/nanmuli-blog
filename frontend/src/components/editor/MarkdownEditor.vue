<script setup lang="ts">
// ref not used in this component
import { computed } from 'vue'
import { MdEditor } from 'md-editor-v3'
import type { ToolbarNames } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { isDarkMode } from '@/styles/themes'

const props = withDefaults(
  defineProps<{
    modelValue: string
    height?: string
  }>(),
  {
    modelValue: '',
    height: '500px'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
  save: [value: string]
}>()

const editorHeight = computed(() => props.height)

function handleChange(value: string): void {
  emit('update:modelValue', value)
  emit('change', value)
}

function handleSave(value: string): void {
  emit('save', value)
}

const toolbars: ToolbarNames[] = [
  'bold',
  'underline',
  'italic',
  'strikeThrough',
  'title',
  'sub',
  'sup',
  'quote',
  'unorderedList',
  'orderedList',
  'codeRow',
  'code',
  'link',
  'image',
  'table',
  'preview',
  'fullscreen',
]
</script>

<template>
  <MdEditor
    :model-value="modelValue"
    :height="editorHeight"
    :toolbars="toolbars"
    :theme="isDarkMode() ? 'dark' : 'light'"
    language="zh-CN"
    @change="handleChange"
    @on-save="handleSave"
  />
</template>
