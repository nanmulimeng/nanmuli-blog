<script setup lang="ts">
import { ref } from 'vue'
import { convertToDailyLog } from '@/api/collector'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  taskId: string
}>()

const emit = defineEmits<{
  (e: 'success', dailyLogId: string): void
}>()

const visible = defineModel<boolean>('visible', { default: false })
const loading = ref(false)

const moods = [
  { value: 'happy', label: '开心', emoji: '😊' },
  { value: 'excited', label: '兴奋', emoji: '🤩' },
  { value: 'normal', label: '平静', emoji: '😌' },
  { value: 'tired', label: '疲惫', emoji: '😮‍💨' },
]

const form = ref<{ mood?: string; weather?: string; logDate?: string; isPublic?: boolean; categoryId?: string }>({
  mood: 'normal',
  isPublic: false,
})

function resetForm(): void {
  form.value = {
    mood: 'normal',
    isPublic: false,
    logDate: new Date().toISOString().slice(0, 10),
  }
}

async function handleSubmit(): Promise<void> {
  loading.value = true
  try {
    const dailyLogId = await convertToDailyLog(props.taskId, form.value)
    ElMessage.success('已转为技术日志')
    visible.value = false
    emit('success', String(dailyLogId))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="转为技术日志"
    width="500px"
    @open="resetForm"
  >
    <el-form :model="form" label-width="80px">
      <el-form-item label="心情">
        <el-radio-group v-model="form.mood">
          <el-radio
            v-for="m in moods"
            :key="m.value"
            :value="m.value"
          >
            {{ m.emoji }} {{ m.label }}
          </el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="天气">
        <el-input v-model="form.weather" placeholder="如：晴、多云" clearable />
      </el-form-item>

      <el-form-item label="日期">
        <el-date-picker
          v-model="form.logDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="选择日期"
          class="w-full"
        />
      </el-form-item>

      <el-form-item label="是否公开">
        <el-switch v-model="form.isPublic" />
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
