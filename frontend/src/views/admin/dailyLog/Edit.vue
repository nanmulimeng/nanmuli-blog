<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getDailyLogById, updateDailyLog } from '@/api/dailyLog'
import type { DailyLogForm } from '@/types/dailyLog'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)

const form = ref<DailyLogForm>({
  logDate: '',
  mood: 'normal',
  weather: '',
  content: '',
  tagIds: [],
})

const moodOptions = [
  { value: 'happy', label: '开心', color: '#f59e0b' },
  { value: 'excited', label: '兴奋', color: '#ef4444' },
  { value: 'normal', label: '平静', color: '#6b7280' },
  { value: 'tired', label: '疲惫', color: '#6366f1' },
]

const rules = {
  logDate: [{ required: true, message: '请选择日期', trigger: 'change' }],
  mood: [{ required: true, message: '请选择心情', trigger: 'change' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

const formRef = ref()
const logId = ref<number>(0)

async function fetchLog(): Promise<void> {
  const id = Number(route.params.id)
  if (!id) {
    router.push('/admin/daily-log')
    return
  }
  logId.value = id

  loading.value = true
  try {
    const log = await getDailyLogById(id)
    form.value = {
      logDate: log.logDate,
      mood: log.mood,
      weather: log.weather || '',
      content: log.content,
      tagIds: log.tagIds || [],
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

onMounted(fetchLog)
</script>

<template>
  <div class="daily-log-edit-page">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">编辑日志</h1>
      <p class="text-gray-500 mt-1">修改技术日志内容</p>
    </div>

    <el-card v-loading="loading" class="max-w-3xl">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent
      >
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <el-form-item label="日期" prop="logDate">
            <el-date-picker
              v-model="form.logDate"
              type="date"
              placeholder="选择日期"
              value-format="YYYY-MM-DD"
              class="w-full"
            />
          </el-form-item>

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
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="12"
            placeholder="记录今天的技术收获..."
            maxlength="5000"
            show-word-limit
          />
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
