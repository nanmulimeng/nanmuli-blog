<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTagList, createTag, updateTag, deleteTag } from '@/api/tag'
import type { Tag } from '@/types/tag'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const tags = ref<Tag[]>([])
const form = ref<Partial<Tag>>({
  name: '',
  slug: '',
  color: '',
  description: '',
  status: 1,
})

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    tags.value = await getTagList()
  } finally {
    loading.value = false
  }
}

function handleCreate(): void {
  isEdit.value = false
  form.value = { name: '', slug: '', color: '', description: '', status: 1 }
  dialogVisible.value = true
}

function handleEdit(row: Tag): void {
  isEdit.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleDelete(row: Tag): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除标签 "${row.name}" 吗？`, '提示', {
      type: 'warning',
    })
    await deleteTag(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消
  }
}

async function handleSubmit(): Promise<void> {
  try {
    if (isEdit.value && form.value.id) {
      await updateTag(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createTag(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch {
    ElMessage.error('操作失败')
  }
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-gray-900">标签管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建标签
      </el-button>
    </div>

    <el-table v-loading="loading" :data="tags" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称">
        <template #default="{ row }">
          <span
            class="rounded px-2 py-1 text-white"
            :style="{ backgroundColor: row.color || '#6b7280' }"
          >
            {{ row.name }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="slug" label="别名" />
      <el-table-column prop="articleCount" label="文章数" width="100" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">
            编辑
          </el-button>
          <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑标签' : '新建标签'">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="form.slug" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
