<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { CopyDocument, Delete, Upload, RefreshRight } from '@element-plus/icons-vue'
import { uploadFile } from '@/api/file'
import type { FileDTO } from '@/api/file'

const props = withDefaults(
  defineProps<{
    modelValue?: string
    accept?: string
    maxSize?: number
    mode?: 'default' | 'cover'
    placeholder?: string
    disabled?: boolean
  }>(),
  {
    modelValue: '',
    accept: 'image/*',
    maxSize: 10,
    mode: 'default',
    placeholder: '输入图片 URL',
    disabled: false,
  }
)

const emit = defineEmits<{
  'update:modelValue': [url: string]
  'upload-success': [file: FileDTO]
  'upload-error': [error: Error]
}>()

const uploading = ref(false)
const previewUrl = ref(props.modelValue || '')

const isImage = computed(() => {
  return props.modelValue || previewUrl.value
})

function handleRemove(): void {
  previewUrl.value = ''
  emit('update:modelValue', '')
}

function handleCopyLink(): void {
  const url = props.modelValue || previewUrl.value
  if (url) {
    navigator.clipboard.writeText(url)
    ElMessage.success('链接已复制')
  }
}

function handleUrlInput(value: string): void {
  previewUrl.value = value
  emit('update:modelValue', value)
}

async function handleUpload(options: { file: File }): Promise<void> {
  const file = options.file
  if (file.size > props.maxSize * 1024 * 1024) {
    ElMessage.warning(`文件大小不能超过 ${props.maxSize}MB`)
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await uploadFile(formData)
    previewUrl.value = res.fileUrl
    emit('update:modelValue', res.fileUrl)
    emit('upload-success', res)
  } catch (error) {
    emit('upload-error', error instanceof Error ? error : new Error('上传失败'))
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="file-upload">
    <!-- Cover Mode: 已有图片时显示预览卡片 -->
    <div v-show="mode === 'cover' && isImage && !uploading" class="cover-preview rounded-xl overflow-hidden border border-border bg-surface-tertiary">
        <div class="relative aspect-[16/9] overflow-hidden">
          <img
            :src="modelValue || previewUrl"
            alt="封面图预览"
            class="h-full w-full object-cover"
            loading="lazy"
          />
          <div
            v-if="uploading"
            class="absolute inset-0 flex items-center justify-center bg-black/40"
          >
            <el-icon class="text-white text-3xl animate-spin"><RefreshRight /></el-icon>
          </div>
        </div>
        <div class="flex items-center justify-end gap-2 px-4 py-2 bg-surface-secondary">
          <el-button size="small" text :icon="CopyDocument" @click="handleCopyLink">
            复制链接
          </el-button>
          <el-button size="small" text type="danger" :icon="Delete" @click="handleRemove">
            移除
          </el-button>
          <el-upload
            :accept="accept"
            :show-file-list="false"
            :http-request="handleUpload"
            :disabled="uploading || disabled"
          >
            <el-button size="small" text :icon="Upload" :loading="uploading">
              重新上传
            </el-button>
          </el-upload>
        </div>
    </div>

    <!-- Default Mode / Cover Mode 未选择图片 -->
    <div v-show="!(mode === 'cover' && isImage && !uploading)" class="upload-area">
        <!-- 拖拽上传区域 -->
        <el-upload
          drag
          :accept="accept"
          :show-file-list="false"
          :http-request="handleUpload"
          :disabled="uploading || disabled"
          class="w-full"
        >
          <div
            class="flex flex-col items-center justify-center py-8 px-4"
            :class="{ 'opacity-50': uploading }"
          >
            <el-icon :size="36" class="text-content-tertiary mb-3" :class="{ 'animate-spin': uploading }">
              <RefreshRight v-if="uploading" />
              <Upload v-else />
            </el-icon>
            <p class="text-sm text-content-secondary">
              {{ uploading ? '上传中...' : '点击上传或拖拽文件到此处' }}
            </p>
            <p class="text-xs text-content-tertiary mt-1">
              支持 {{ accept.replace('image/', '').replace(/,/g, '/') }}，最大 {{ maxSize }}MB
            </p>
          </div>
        </el-upload>

        <!-- 分隔文字 -->
        <div class="flex items-center gap-3 my-3">
          <div class="flex-1 border-t border-border" />
          <span class="text-xs text-content-tertiary">或</span>
          <div class="flex-1 border-t border-border" />
        </div>

        <!-- URL 输入 -->
        <el-input
          :model-value="modelValue"
          :placeholder="placeholder"
          :disabled="disabled"
          clearable
          @input="handleUrlInput"
          @clear="handleRemove"
        />
      </div>
  </div>
</template>

<style scoped>
.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
