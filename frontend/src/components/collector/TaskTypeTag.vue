<script setup lang="ts">
import { CollectTaskTypeMap } from '@/types/collector'

defineProps<{
  taskType: string
}>()
</script>

<template>
  <el-tag :type="CollectTaskTypeMap[taskType]?.type || 'info'" size="small">
    {{ CollectTaskTypeMap[taskType]?.label || taskType }}
  </el-tag>
</template>
