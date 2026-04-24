<script setup lang="ts">
import { CollectTaskStatusMap } from '@/types/collector'
import { Loading } from '@element-plus/icons-vue'

defineProps<{
  status: number
  showIcon?: boolean
}>()
</script>

<template>
  <el-tag :type="CollectTaskStatusMap[status]?.type || 'info'" size="small">
    <div class="flex items-center gap-1">
      <el-icon v-if="showIcon && (status === 1 || status === 2)" :size="12" class="animate-spin">
        <Loading />
      </el-icon>
      {{ CollectTaskStatusMap[status]?.label || '未知' }}
    </div>
  </el-tag>
</template>
