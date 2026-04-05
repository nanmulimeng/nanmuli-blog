<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAdminDailyLogById, updateDailyLog } from '@/api/dailyLog'
import { getLeafCategoryList } from '@/api/category'
import MarkdownEditor from '@/components/editor/MarkdownEditor.vue'
import type { DailyLog, DailyLogForm } from '@/types/dailyLog'
import type { Category } from '@/types/category'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const categories = ref<Category[]>([])

const form = ref<DailyLogForm>({
  logDate: '',
  mood: 'normal',
  weather: '',
  content: '',
  isPublic: false,
  categoryId: undefined,
})

const moodOptions = [
  { value: 'happy', label: '开心', color: '#f59e0b' },
  { value: 'excited', label: '兴奋', color: '#ef4444' },
  { value: 'normal', label: '平静', color: '#64748B' },
  { value: 'tired', label: '疲惫', color: '#3B82F6' },
]

const rules = {
  logDate: [{ required: true, message: '请选择日期', trigger: 'change' }],
  mood: [{ required: true, message: '请选择心情', trigger: 'change' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

const formRef = ref()
const logId = ref<string>('')

async function fetchLog(): Promise<void> {
  const id = route.params.id as string
  if (!id) {
    router.push('/admin/daily-log')
    return
  }
  logId.value = id

  loading.value = true
  try {
    const log: DailyLog = await getAdminDailyLogById(id)
    form.value = {
      logDate: log.logDate,
      mood: log.mood,
      weather: log.weather || '',
      content: log.content || '',
      isPublic: log.isPublic ?? false,
      categoryId: log.categoryId,
    }
  } catch {
    router.push('/admin/daily-log')
  } finally {
    loading.value = false
  }
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await updateDailyLog(logId.value, form.value)
    ElMessage.success('更新成功')
    router.push('/admin/daily-log')
  } finally {
    saving.value = false
  }
}

function handleCancel(): void {
  router.push('/admin/daily-log')
}

async function fetchCategories() {
  try {
    categories.value = await getLeafCategoryList()
  } catch {
    ElMessage.error('加载分类失败')
  }
}

onMounted(() => {
  fetchLog()
  fetchCategories()
})
</script>

<template>
  <div class="daily-log-edit-page">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-content-primary">编辑日志</h1>
      <p class="text-content-secondary mt-1">修改技术日志内容</p>
    </div>

    <el-card v-loading="loading" class="max-w-3xl">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent
      >
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <el-form-item label="日期" prop="logDate">
            <el-date-picker
              v-model="form.logDate"
              type="date"
              placeholder="选择日期"
              value-format="YYYY-MM-DD"
              class="w-full"
            />
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
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <el-form-item label="心情" prop="mood">
            <el-select v-model="form.mood" placeholder="选择心情" class="w-full">
              <el-option
                v-for="item in moodOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              >
                <div class="flex items-center gap-2">
                  <span
                    class="w-3 h-3 rounded-full"
                    :style="{ backgroundColor: item.color }"
                  />
                  <span>{{ item.label }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>

          <el-form-item label="天气">
            <el-input
              v-model="form.weather"
              placeholder="例如：晴 25°C"
              maxlength="20"
              show-word-limit
            />
          </el-form-item>
        </div>

        <el-form-item label="内容" prop="content">
          <MarkdownEditor v-model="form.content" height="400px" />
        </el-form-item>

        <el-form-item label="分享设置">
          <div class="flex items-center gap-4">
            <el-switch
              v-model="form.isPublic"
              active-text="公开分享"
              inactive-text="私有"
            />
            <span class="text-xs text-content-tertiary">
              {{ form.isPublic ? '其他人可以通过链接查看此日志' : '仅管理员可见' }}
            </span>
          </div>
        </el-form-item>

        <el-form-item>
          <div class="flex justify-end gap-3">
            <el-button @click="handleCancel">取消</el-button>
            <el-button type="primary" :loading="saving" @click="handleSubmit">
              保存修改
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
