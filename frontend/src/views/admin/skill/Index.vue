<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminSkillList, createSkill, updateSkill, deleteSkill } from '@/api/skill'
import type { Skill } from '@/types/skill'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const skills = ref<Skill[]>([])
const formRef = ref()

const form = ref<Partial<Skill>>({
  name: '',
  category: 'language',
  proficiency: 3,
  icon: '',
  color: '#409EFF',
  description: '',
  sort: 0,
  status: 1,
})

const rules = {
  name: [{ required: true, message: '请输入技能名称', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
}

const categoryOptions = [
  { label: '编程语言', value: 'language' },
  { label: '框架', value: 'framework' },
  { label: '工具', value: 'tool' },
  { label: '其他', value: 'other' },
]

// 分类映射
const categoryMap: Record<string, string> = {
  language: '编程语言',
  framework: '框架',
  tool: '工具',
  other: '其他',
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    skills.value = await getAdminSkillList()
  } catch (error: any) {
    ElMessage.error(error?.message || '加载技能列表失败')
  } finally {
    loading.value = false
  }
}

function handleCreate(): void {
  isEdit.value = false
  form.value = {
    name: '',
    category: 'language',
    proficiency: 3,
    icon: '',
    color: '#409EFF',
    description: '',
    sort: 0,
    status: 1,
  }
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
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') {
      return
    }
    const msg = error?.response?.data?.message || error?.message || '删除失败'
    ElMessage.error(msg)
  }
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

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
  } catch (error: any) {
    const msg = error?.response?.data?.message || error?.message || '操作失败'
    ElMessage.error(msg)
  }
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-content-primary">技能管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建技能
      </el-button>
    </div>

    <el-empty v-if="!loading && skills.length === 0" description="暂无技能" />

    <el-table v-if="skills.length > 0" v-loading="loading" :data="skills" border>
      <el-table-column type="index" label="#" width="50" />

      <el-table-column prop="name" label="名称" min-width="120">
        <template #default="{ row }">
          <div class="flex items-center gap-2">
            <el-tag
              v-if="row.color"
              :color="row.color"
              effect="dark"
              size="small"
              class="w-3 h-3 rounded-full"
            />
            <span>{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="分类" width="100">
        <template #default="{ row }">
          <el-tag size="small" type="info">
            {{ categoryMap[row.category] || row.category }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="熟练度" width="140">
        <template #default="{ row }">
          <el-rate
            :model-value="row.proficiency"
            disabled
            :colors="['#F7BA2A', '#F7BA2A', '#F7BA2A']"
            void-color="#C6D1DE"
          />
        </template>
      </el-table-column>

      <el-table-column prop="sort" label="排序" width="70" align="center" />

      <el-table-column label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '显示' : '隐藏' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="150" fixed="right" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button type="primary" :icon="Edit" size="small" @click="handleEdit(row)" title="编辑" />
            <el-button type="danger" :icon="Delete" size="small" @click="handleDelete(row)" title="删除" />
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑技能' : '新建技能'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入技能名称" />
        </el-form-item>

        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category" class="w-full">
            <el-option
              v-for="opt in categoryOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="熟练度" prop="proficiency">
          <el-rate v-model="form.proficiency" :max="5" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="颜色" prop="color">
              <el-color-picker v-model="form.color" :predefine="['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399', '#FF6B6B', '#4ECDC4']" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio :value="1">显示</el-radio>
                <el-radio :value="0">隐藏</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" />
          <span class="ml-2 text-xs text-gray-500">数字越小排序越靠前</span>
        </el-form-item>

        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入技能描述" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 修复熟练度评分后的小点 */
:deep(.el-rate__item:last-child .el-rate__icon) {
  margin-right: 0;
}

:deep(.el-rate__decimal) {
  display: none;
}
</style>
