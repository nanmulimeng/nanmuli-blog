<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProjectList, createProject, updateProject, deleteProject } from '@/api/project'
import type { Project } from '@/types/project'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const projects = ref<Project[]>([])
const form = ref<Partial<Project>>({
  name: '',
  slug: '',
  description: '',
  cover: '',
  githubUrl: '',
  demoUrl: '',
  docUrl: '',
  techStack: [],
  sort: 0,
  status: 1,
})

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    projects.value = await getProjectList()
  } finally {
    loading.value = false
  }
}

function handleCreate(): void {
  isEdit.value = false
  form.value = {
    name: '',
    slug: '',
    description: '',
    cover: '',
    githubUrl: '',
    demoUrl: '',
    docUrl: '',
    techStack: [],
    sort: 0,
    status: 1,
  }
  dialogVisible.value = true
}

function handleEdit(row: Project): void {
  isEdit.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleDelete(row: Project): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除项目 "${row.name}" 吗？`, '提示', {
      type: 'warning',
    })
    await deleteProject(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消
  }
}

async function handleSubmit(): Promise<void> {
  try {
    if (isEdit.value && form.value.id) {
      await updateProject(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createProject(form.value)
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
      <h2 class="text-xl font-bold text-gray-900">项目管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建项目
      </el-button>
    </div>

    <el-table v-loading="loading" :data="projects" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" show-overflow-tooltip />
      <el-table-column prop="sort" label="排序" width="100" />
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑项目' : '新建项目'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="form.slug" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="封面图">
          <el-input v-model="form.cover" placeholder="封面图URL" />
        </el-form-item>
        <el-form-item label="GitHub">
          <el-input v-model="form.githubUrl" placeholder="GitHub链接" />
        </el-form-item>
        <el-form-item label="演示链接">
          <el-input v-model="form.demoUrl" placeholder="演示地址" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
