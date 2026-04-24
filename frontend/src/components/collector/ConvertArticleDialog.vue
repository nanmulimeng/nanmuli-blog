<script setup lang="ts">
import { ref } from 'vue'
import { convertToArticle } from '@/api/collector'
import { getLeafCategoryList } from '@/api/category'
import type { Category } from '@/types/category'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  taskId: string
  aiTitle?: string | null
}>()

const emit = defineEmits<{
  (e: 'success', articleId: string): void
}>()

const visible = defineModel<boolean>('visible', { default: false })
const loading = ref(false)
const categories = ref<Category[]>([])

const form = ref<{ title?: string; categoryId?: string }>({})

async function handleOpen(): Promise<void> {
  form.value = { title: props.aiTitle || undefined }
  if (categories.value.length === 0) {
    try {
      categories.value = await getLeafCategoryList()
    } catch { /* non-critical */ }
  }
}

async function handleSubmit(): Promise<void> {
  loading.value = true
  try {
    const articleId = await convertToArticle(props.taskId, form.value)
    ElMessage.success('已转为文章草稿')
    visible.value = false
    emit('success', String(articleId))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="转为文章草稿"
    width="500px"
    @open="handleOpen"
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="文章标题">
        <el-input
          v-model="form.title"
          :placeholder="aiTitle || '请输入文章标题'"
          maxlength="200"
          show-word-limit
          clearable
        />
        <div v-if="aiTitle" class="mt-1 text-xs text-content-tertiary">
          留空则使用 AI 生成标题
        </div>
      </el-form-item>

      <el-form-item label="文章分类">
        <el-select v-model="form.categoryId" placeholder="选择分类（可选）" clearable class="w-full">
          <el-option
            v-for="cat in categories"
            :key="cat.id"
            :label="cat.name"
            :value="cat.id"
          />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        确认转换
      </el-button>
    </template>
  </el-dialog>
</template>
