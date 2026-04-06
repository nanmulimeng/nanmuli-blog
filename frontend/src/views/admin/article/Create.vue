<script setup lang="ts">
import { reactive, ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createArticle } from '@/api/article'
import { getLeafCategoryList } from '@/api/category'
import MarkdownEditor from '@/components/editor/MarkdownEditor.vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { Category } from '@/types/category'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const categories = ref<Category[]>([])

const form = reactive({
  title: '',
  content: '',
  summary: '',
  cover: '',
  categoryId: undefined as string | undefined,
  isTop: false,
  isOriginal: true,
  originalUrl: '',
  status: 1,
})

// 自动保存相关
const DRAFT_KEY = 'article_draft_create'
const DRAFT_TIME_KEY = 'article_draft_create_time'
let autoSaveInterval: number | null = null

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

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

async function fetchCategories() {
  try {
    categories.value = await getLeafCategoryList()
  } catch {
    ElMessage.error('加载分类失败')
  }
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value || loading.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await createArticle(form)
      hasUnsavedChanges.value = false // 重置未保存标记
      clearDraft() // 发布成功后清除草稿
      ElMessage.success('创建成功')
      router.push('/admin/article')
    } catch {
      ElMessage.error('创建失败')
    } finally {
      loading.value = false
    }
  })
}

function handleCancel(): void {
  router.back()
}

onMounted(() => {
  fetchCategories()
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
      <h2 class="text-xl font-bold text-content-primary">新建文章</h2>
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
        <el-select v-model="form.categoryId" filterable placeholder="选择分类" clearable class="w-full">
          <el-option
            v-for="cat in categories"
            :key="cat.id"
            :label="cat.name"
            :value="cat.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="摘要">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="3"
          placeholder="文章摘要，留空自动生成"
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
          <el-radio :value="1">立即发布</el-radio>
          <el-radio :value="2">保存为草稿</el-radio>
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
