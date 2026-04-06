<script setup lang="ts">
import { reactive, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getArticleById, updateArticle } from '@/api/article'
import { getLeafCategoryList } from '@/api/category'
import MarkdownEditor from '@/components/editor/MarkdownEditor.vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { Article } from '@/types/article'
import type { Category } from '@/types/category'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const categories = ref<Category[]>([])
const articleId = route.params.id as string

const form = reactive<Partial<Article>>({
  title: '',
  content: '',
  summary: '',
  cover: '',
  categoryId: undefined,
  isTop: false,
  isOriginal: true,
  originalUrl: '',
  status: 1,
})

// 自动保存相关
const DRAFT_KEY = `article_draft_edit_${articleId}`
const DRAFT_TIME_KEY = `article_draft_edit_time_${articleId}`
let autoSaveInterval: number | null = null

// 恢复草稿
function restoreDraft() {
  const draft = localStorage.getItem(DRAFT_KEY)
  const draftTime = localStorage.getItem(DRAFT_TIME_KEY)
  if (draft && draftTime) {
    const hours = (Date.now() - parseInt(draftTime)) / 3600000
    if (hours < 24) {
      ElMessageBox.confirm('检测到有未提交的草稿，是否恢复？', '提示', {
        confirmButtonText: '恢复',
        cancelButtonText: '放弃',
        type: 'info',
      })
        .then(() => {
          const draftData = JSON.parse(draft)
          Object.assign(form, draftData)
          ElMessage.success('草稿已恢复')
        })
        .catch(() => {
          localStorage.removeItem(DRAFT_KEY)
          localStorage.removeItem(DRAFT_TIME_KEY)
        })
    } else {
      localStorage.removeItem(DRAFT_KEY)
      localStorage.removeItem(DRAFT_TIME_KEY)
    }
  }
}

// 自动保存
function startAutoSave() {
  autoSaveInterval = window.setInterval(() => {
    if (form.title || form.content) {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(form))
      localStorage.setItem(DRAFT_TIME_KEY, Date.now().toString())
    }
  }, 30000) // 每30秒保存一次
}

// 清除草稿
function clearDraft() {
  localStorage.removeItem(DRAFT_KEY)
  localStorage.removeItem(DRAFT_TIME_KEY)
  if (autoSaveInterval) {
    clearInterval(autoSaveInterval)
    autoSaveInterval = null
  }
}

// 未保存修改标记
const hasUnsavedChanges = ref(false)

// 监听表单变化
watch(form, () => {
  hasUnsavedChanges.value = true
}, { deep: true, flush: 'post' })

// 浏览器原生离开提示
function handleBeforeUnload(e: BeforeUnloadEvent) {
  if (hasUnsavedChanges.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

async function fetchArticle(): Promise<void> {
  try {
    const article = await getArticleById(articleId)
    // 确保 content 不为 null/undefined
    form.title = article.title || ''
    form.content = article.content || ''
    form.summary = article.summary || ''
    form.cover = article.cover || ''
    form.categoryId = article.category?.id || undefined
    form.isTop = article.isTop ?? false
    form.isOriginal = article.isOriginal ?? true
    form.originalUrl = article.originalUrl || ''
    form.status = article.status ?? 1
  } catch {
    ElMessage.error('加载文章失败')
  }
}

async function fetchCategories() {
  try {
    const res = await getLeafCategoryList()
    categories.value = res
  } catch (error) {
    console.error('加载分类失败:', error)
    ElMessage.error('加载分类失败')
  }
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value || loading.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await updateArticle(articleId, form)
      hasUnsavedChanges.value = false // 重置未保存标记
      clearDraft() // 更新成功后清除草稿
      ElMessage.success('更新成功')
      router.push('/admin/article')
    } catch {
      ElMessage.error('更新失败')
    } finally {
      loading.value = false
    }
  })
}

function handleCancel(): void {
  router.back()
}

onMounted(async () => {
  await fetchCategories()
  await fetchArticle()
  restoreDraft()
  startAutoSave()
  window.addEventListener('beforeunload', handleBeforeUnload)
})

onBeforeUnmount(() => {
  if (autoSaveInterval) {
    clearInterval(autoSaveInterval)
  }
  window.removeEventListener('beforeunload', handleBeforeUnload)
})

// 路由离开守卫
onBeforeRouteLeave((_to, _from, next) => {
  if (hasUnsavedChanges.value) {
    ElMessageBox.confirm('有未保存的修改，确定要离开吗？', '提示', {
      confirmButtonText: '离开',
      cancelButtonText: '取消',
      type: 'warning',
    })
      .then(() => {
        next()
      })
      .catch(() => {
        next(false)
      })
  } else {
    next()
  }
})
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-content-primary">编辑文章</h2>
    </div>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      class="max-w-4xl"
    >
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="请输入文章标题" maxlength="200" show-word-limit />
      </el-form-item>

      <el-form-item label="分类">
        <el-select
          v-model="form.categoryId"
          filterable
          placeholder="选择分类"
          clearable
          class="w-full"
        >
          <el-option
            v-for="cat in categories"
            :key="cat.id"
            :label="cat.name"
            :value="cat.id"
          >
            {{ cat.name }}
          </el-option>
        </el-select>
      </el-form-item>

      <el-form-item label="摘要">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="3"
          placeholder="文章摘要"
          maxlength="500"
          show-word-limit
        />
      </el-form-item>

      <el-form-item label="封面图">
        <el-input v-model="form.cover" placeholder="封面图URL" maxlength="500" />
      </el-form-item>

      <el-form-item label="内容" prop="content">
        <MarkdownEditor v-model="form.content" height="500px" />
      </el-form-item>

      <el-form-item>
        <el-checkbox v-model="form.isTop">置顶文章</el-checkbox>
        <el-checkbox v-model="form.isOriginal">原创文章</el-checkbox>
      </el-form-item>

      <el-form-item v-if="!form.isOriginal" label="原文链接">
        <el-input v-model="form.originalUrl" placeholder="转载文章的原文链接" maxlength="500" />
      </el-form-item>

      <el-form-item label="发布状态">
        <el-radio-group v-model="form.status">
          <el-radio :value="1">已发布</el-radio>
          <el-radio :value="2">草稿</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" :loading="loading" @click="handleSubmit">
          保存
        </el-button>
        <el-button @click="handleCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>
