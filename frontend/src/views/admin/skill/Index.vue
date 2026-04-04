<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getSkillList, createSkill, updateSkill, deleteSkill } from '@/api/skill'
import type { Skill } from '@/types/skill'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const skills = ref<Skill[]>([])
const form = ref<Partial<Skill>>({
  name: '',
  category: 'language',
  proficiency: 3,
  icon: '',
  color: '',
  description: '',
  sort: 0,
  status: 1,
})

const categoryOptions = [
  { label: '编程语言', value: 'language' },
  { label: '框架', value: 'framework' },
  { label: '工具', value: 'tool' },
  { label: '其他', value: 'other' },
]

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    skills.value = await getSkillList()
  } finally {
    loading.value = false
  }
}

function handleCreate(): void {
  isEdit.value = false
  form.value = { name: '', category: 'language', proficiency: 3, sort: 0, status: 1 }
  dialogVisible.value = true
}

function handleEdit(row: Skill): void {
  isEdit.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleDelete(row: Skill): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除技能 "${row.name}" 吗？`, '提示', {
      type: 'warning',
    })
    await deleteSkill(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch {
    // 用户取消
  }
}

async function handleSubmit(): Promise<void> {
  try {
    if (isEdit.value && form.value.id) {
      await updateSkill(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createSkill(form.value)
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
      <h2 class="text-xl font-bold text-gray-900">技能管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建技能
      </el-button>
    </div>

    <el-table v-loading="loading" :data="skills" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="category" label="分类" />
      <el-table-column prop="proficiency" label="熟练度" width="120">
        <template #default="{ row }">
          <el-rate :model-value="row.proficiency" disabled />
        </template>
      </el-table-column>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑技能' : '新建技能'">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category">
            <el-option
              v-for="opt in categoryOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="熟练度">
          <el-rate v-model="form.proficiency" :max="5" />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
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
