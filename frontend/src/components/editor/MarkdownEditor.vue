<script setup lang="ts">
import { ref } from 'vue'
import MdEditor from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

const props = defineProps<{
  modelValue: string
  height?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
  save: [value: string]
}>()

const editorHeight = props.height || '500px'

function handleChange(value: string): void {
  emit('update:modelValue', value)
  emit('change', value)
}

function handleSave(value: string): void {
  emit('save', value)
}

const toolbars = [
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
    :theme="'light'"
    language="zh-CN"
    @change="handleChange"
    @on-save="handleSave"
  />
</template>
