<script setup lang="ts">
import { CollectTaskStatusMap } from '@/types/collector'
import { Refresh } from '@element-plus/icons-vue'

defineProps<{
  status: number
}>()
</script>

<template>
  <el-tag :type="CollectTaskStatusMap[status]?.type || 'info'" size="small">
    <div class="flex items-center gap-1">
      <el-icon v-if="status === 1 || status === 2" :size="12" class="animate-spin">
        <Refresh />
      </el-icon>
      {{ CollectTaskStatusMap[status]?.label || '未知' }}
    </div>
  </el-tag>
</template>
