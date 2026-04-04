<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getArticleList, updateArticle } from '@/api/article'
import type { FormInstance, FormRules } from 'element-plus'
import type { Article } from '@/types/article'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const articleId = Number(route.params.id)

const form = reactive<Partial<Article>>({
  title: '',
  slug: '',
  content: '',
  summary: '',
  cover: '',
  categoryId: undefined,
  isTop: false,
  isOriginal: true,
  originalUrl: '',
  status: 1,
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

async function fetchArticle(): Promise<void> {
  try {
    // TODO: 通过ID获取文章详情
    const res = await getArticleList({ current: 1, size: 1 })
    const article = res.records.find(a => a.id === articleId)
    if (article) {
      Object.assign(form, article)
    }
  } catch {
    ElMessage.error('加载文章失败')
  }
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await updateArticle(articleId, form)
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

onMounted(fetchArticle)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-gray-900">编辑文章</h2>
    </div>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      class="max-w-4xl"
    >
      <el-form-item label="标题" prop="title">
        <el-input v-model="form.title" placeholder="请输入文章标题" />
      </el-form-item>

      <el-form-item label="别名 (slug)">
        <el-input v-model="form.slug" placeholder="用于URL" />
      </el-form-item>

      <el-form-item label="分类">
        <el-select v-model="form.categoryId" placeholder="选择分类" clearable>
          <!-- TODO: 加载分类列表 -->
        </el-select>
      </el-form-item>

      <el-form-item label="摘要">
        <el-input
          v-model="form.summary"
          type="textarea"
          :rows="3"
          placeholder="文章摘要"
        />
      </el-form-item>

      <el-form-item label="封面图">
        <el-input v-model="form.cover" placeholder="封面图URL" />
      </el-form-item>

      <el-form-item label="内容" prop="content">
        <md-editor-v3
          v-model="form.content"
          :theme="'light'"
          style="height: 500px"
        />
      </el-form-item>

      <el-form-item>
        <el-checkbox v-model="form.isTop">置顶文章</el-checkbox>
        <el-checkbox v-model="form.isOriginal">原创文章</el-checkbox>
      </el-form-item>

      <el-form-item v-if="!form.isOriginal" label="原文链接">
        <el-input v-model="form.originalUrl" placeholder="转载文章的原文链接" />
      </el-form-item>

      <el-form-item label="发布状态">
        <el-radio-group v-model="form.status">
          <el-radio :label="1">已发布</el-radio>
          <el-radio :label="2">草稿</el-radio>
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
