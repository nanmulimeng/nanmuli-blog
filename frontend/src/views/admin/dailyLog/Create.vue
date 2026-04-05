<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createDailyLog } from '@/api/dailyLog'
import MarkdownEditor from '@/components/editor/MarkdownEditor.vue'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  content: '',
  mood: 'normal' as const,
  weather: '',
  tags: [] as string[],
  logDate: new Date().toISOString().split('T')[0],
})

const rules: FormRules = {
  content: [{ required: true, message: '请输入日志内容', trigger: 'blur' }],
  logDate: [{ required: true, message: '请选择日期', trigger: 'blur' }],
}

const moodOptions = [
  { label: '开心', value: 'happy', color: '#f59e0b' },
  { label: '兴奋', value: 'excited', color: '#ef4444' },
  { label: '平静', value: 'normal', color: '#64748B' },
  { label: '疲惫', value: 'tired', color: '#3B82F6' },
]

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      await createDailyLog(form)
      ElMessage.success('创建成功')
      router.push('/admin/daily-log')
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
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-content-primary">新建日志</h2>
    </div>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="80px"
      class="max-w-4xl"
    >
      <el-form-item label="日期" prop="logDate">
        <el-date-picker
          v-model="form.logDate"
          type="date"
          placeholder="选择日期"
          value-format="YYYY-MM-DD"
        />
      </el-form-item>

      <el-form-item label="心情" prop="mood">
        <el-radio-group v-model="form.mood">
          <el-radio
            v-for="opt in moodOptions"
            :key="opt.value"
            :value="opt.value"
          >
            <span class="inline-flex items-center gap-1">
              <span
                class="h-3 w-3 rounded-full"
                :style="{ backgroundColor: opt.color }"
              />
              {{ opt.label }}
            </span>
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="天气" prop="weather">
        <el-input v-model="form.weather" placeholder="例如：晴天 25°C" />
      </el-form-item>

      <el-form-item label="标签" prop="tags">
        <el-select
          v-model="form.tags"
          multiple
          filterable
          allow-create
          placeholder="添加标签"
        />
      </el-form-item>

      <el-form-item label="内容" prop="content">
        <MarkdownEditor v-model="form.content" height="400px" />
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
