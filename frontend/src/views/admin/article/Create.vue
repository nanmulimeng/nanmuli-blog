<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
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
  slug: '',
  content: '',
  summary: '',
  cover: '',
  categoryId: undefined as string | undefined,
  isTop: false,
  isOriginal: true,
  originalUrl: '',
  status: 1,
})

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
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await createArticle(form)
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
        <el-input v-model="form.title" placeholder="请输入文章标题" />
      </el-form-item>

      <el-form-item label="别名 (slug)">
        <el-input v-model="form.slug" placeholder="用于URL，留空自动生成" />
      </el-form-item>

      <el-form-item label="分类">
        <el-select v-model="form.categoryId" placeholder="选择分类" clearable class="w-full">
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
        />
      </el-form-item>

      <el-form-item label="封面图">
        <el-input v-model="form.cover" placeholder="封面图URL" />
      </el-form-item>

      <el-form-item label="内容" prop="content">
        <MarkdownEditor v-model="form.content" height="500px" />
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
