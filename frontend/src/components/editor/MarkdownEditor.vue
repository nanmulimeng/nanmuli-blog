<script setup lang="ts">
import { computed, ref } from 'vue'
import { MdEditor } from 'md-editor-v3'
import type { ToolbarNames } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'
import { isDarkMode } from '@/styles/themes'
import { uploadFile } from '@/api/file'

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
const uploading = ref(false)

function handleChange(value: string): void {
  emit('update:modelValue', value)
  emit('change', value)
}

function handleSave(value: string): void {
  emit('save', value)
}

async function handleUploadImg(
  files: File[],
  callback: (urls: string[]) => void
): Promise<void> {
  uploading.value = true
  try {
    const results = await Promise.all(
      files.map(async (file) => {
        const formData = new FormData()
        formData.append('file', file)
        const res = await uploadFile(formData)
        return res.fileUrl
      })
    )
    callback(results)
  } finally {
    uploading.value = false
  }
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
  <div>
    <MdEditor
      :model-value="modelValue"
      :height="editorHeight"
      :toolbars="toolbars"
      :theme="isDarkMode() ? 'dark' : 'light'"
      language="zh-CN"
      :on-upload-img="handleUploadImg"
      @change="handleChange"
      @on-save="handleSave"
    />
    <div v-if="uploading" class="mt-2">
      <el-alert title="图片上传中..." type="info" :closable="false" />
    </div>
  </div>
</template>
