<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminProjectList, createProject, updateProject, deleteProject } from '@/api/project'
import type { Project } from '@/types/project'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const projects = ref<Project[]>([])
const formRef = ref()

const form = ref<Partial<Project>>({
  name: '',
  description: '',
  cover: '',
  githubUrl: '',
  demoUrl: '',
  docUrl: '',
  techStack: [],
  screenshots: [],
  startDate: '',
  endDate: '',
  sort: 0,
  status: 1,
})

// 技术栈标签输入
const techStackInput = ref('')

// 表单验证规则
const rules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在2-100个字符', trigger: 'blur' }
  ],
  githubUrl: [
    { pattern: /^https?:\/\/.*/, message: '必须以http://或https://开头', trigger: 'blur' }
  ],
  demoUrl: [
    { pattern: /^https?:\/\/.*/, message: '必须以http://或https://开头', trigger: 'blur' }
  ],
  docUrl: [
    { pattern: /^https?:\/\/.*/, message: '必须以http://或https://开头', trigger: 'blur' }
  ],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    projects.value = await getAdminProjectList()
  } catch (error: any) {
    ElMessage.error(error?.message || '加载项目列表失败')
  } finally {
    loading.value = false
  }
}

function handleCreate(): void {
  isEdit.value = false
  form.value = {
    name: '',
    description: '',
    cover: '',
    githubUrl: '',
    demoUrl: '',
    docUrl: '',
    techStack: [],
    screenshots: [],
    startDate: '',
    endDate: '',
    sort: 0,
    status: 1,
  }
  techStackInput.value = ''
  dialogVisible.value = true
}

function handleEdit(row: Project): void {
  isEdit.value = true
  // 深拷贝避免直接修改表格数据
  form.value = {
    ...row,
    techStack: row.techStack ? [...row.techStack] : [],
    screenshots: row.screenshots ? [...row.screenshots] : [],
  }
  techStackInput.value = ''
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
  } catch (error: any) {
    if (error === 'cancel' || error?.message === 'cancel') {
      return
    }
    const msg = error?.response?.data?.message || error?.message || '删除失败'
    ElMessage.error(msg)
  }
}

// 添加技术栈标签
function handleAddTechStack(): void {
  const tag = techStackInput.value.trim()
  if (!tag) return
  if (form.value.techStack?.includes(tag)) {
    ElMessage.warning('该技术栈已存在')
    return
  }
  form.value.techStack?.push(tag)
  techStackInput.value = ''
}

// 移除技术栈标签
function handleRemoveTechStack(tag: string): void {
  const index = form.value.techStack?.indexOf(tag)
  if (index !== undefined && index > -1) {
    form.value.techStack?.splice(index, 1)
  }
}

// 日期范围校验
function validateDateRange(): boolean {
  if (form.value.startDate && form.value.endDate) {
    if (new Date(form.value.endDate) < new Date(form.value.startDate)) {
      ElMessage.error('结束日期不能早于开始日期')
      return false
    }
  }
  return true
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  // 额外校验日期范围
  if (!validateDateRange()) return

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
      <h2 class="text-xl font-bold text-content-primary">项目管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建项目
      </el-button>
    </div>

    <el-empty v-if="!loading && projects.length === 0" description="暂无项目" />

    <el-table v-if="projects.length > 0" v-loading="loading" :data="projects" border>
      <el-table-column type="index" label="#" width="50" />
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="slug" label="别名" width="120" />
      <el-table-column label="技术栈" min-width="150">
        <template #default="{ row }">
          <el-tag
            v-for="tag in row.techStack?.slice(0, 3)"
            :key="tag"
            size="small"
            class="mr-1"
          >
            {{ tag }}
          </el-tag>
          <el-tag v-if="row.techStack?.length > 3" size="small" type="info">
            +{{ row.techStack.length - 3 }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间范围" width="180">
        <template #default="{ row }">
          <div v-if="row.startDate" class="text-xs">
            <div>{{ row.startDate }}</div>
            <div v-if="row.endDate">~ {{ row.endDate }}</div>
            <div v-else class="text-gray-400">至今</div>
          </div>
          <span v-else class="text-gray-400">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="sort" label="排序" width="70" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '显示' : '隐藏' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button type="primary" :icon="Edit" size="small" @click="handleEdit(row)" title="编辑" />
            <el-button type="danger" :icon="Delete" size="small" @click="handleDelete(row)" title="删除" />
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑项目' : '新建项目'"
      width="700px"
      class="theme-dialog"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        class="theme-form"
      >
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入项目名称" />
        </el-form-item>

        <el-form-item label="项目描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="请输入项目描述"
          />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="封面图URL" prop="cover">
              <el-input v-model="form.cover" placeholder="封面图URL" />
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

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="startDate">
              <el-date-picker
                v-model="form.startDate"
                type="date"
                placeholder="选择开始日期"
                value-format="YYYY-MM-DD"
                class="w-full"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="endDate">
              <el-date-picker
                v-model="form.endDate"
                type="date"
                placeholder="选择结束日期（可选）"
                value-format="YYYY-MM-DD"
                class="w-full"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="技术栈" prop="techStack">
          <div class="flex flex-wrap gap-2 mb-2">
            <el-tag
              v-for="tag in form.techStack"
              :key="tag"
              closable
              @close="handleRemoveTechStack(tag)"
            >
              {{ tag }}
            </el-tag>
          </div>
          <el-input
            v-model="techStackInput"
            placeholder="输入技术栈按回车添加，如Vue、Spring Boot"
            @keyup.enter="handleAddTechStack"
          >
            <template #append>
              <el-button @click="handleAddTechStack">添加</el-button>
            </template>
          </el-input>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="GitHub" prop="githubUrl">
              <el-input v-model="form.githubUrl" placeholder="https://github.com/..." />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="演示链接" prop="demoUrl">
              <el-input v-model="form.demoUrl" placeholder="https://..." />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="文档链接" prop="docUrl">
          <el-input v-model="form.docUrl" placeholder="https://..." />
        </el-form-item>

        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" />
          <span class="ml-2 text-xs text-gray-500">数字越小排序越靠前</span>
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
/* 表格样式已由全局样式处理 */
</style>
