<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Delete, Edit, Link, Plus, View } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createFriendLink,
  deleteFriendLink,
  getAdminFriendLinkList,
  updateFriendLink,
} from '@/api/friendLink'
import type { FriendLink } from '@/types/friendLink'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const links = ref<FriendLink[]>([])
const formRef = ref()

const form = ref<Partial<FriendLink>>({
  name: '',
  url: '',
  logo: '',
  description: '',
  email: '',
  sort: 0,
  status: 1,
})

const rules = {
  name: [
    { required: true, message: '请输入网站名称', trigger: 'blur' },
    { max: 50, message: '网站名称不能超过50字符', trigger: 'blur' },
  ],
  url: [
    { required: true, message: '请输入网站链接', trigger: 'blur' },
    { pattern: /^https?:\/\/.+/, message: '链接必须以 http:// 或 https:// 开头', trigger: 'blur' },
  ],
  logo: [
    { pattern: /^$|^https?:\/\/.+/, message: 'Logo 必须以 http:// 或 https:// 开头', trigger: 'blur' },
  ],
  email: [
    { pattern: /^$|^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: '邮箱格式不正确', trigger: 'blur' },
  ],
}

async function fetchData(): Promise<void> {
  loading.value = true
  try {
    links.value = await getAdminFriendLinkList()
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '加载友链列表失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function resetForm(): void {
  form.value = {
    name: '',
    url: '',
    logo: '',
    description: '',
    email: '',
    sort: 0,
    status: 1,
  }
}

function handleCreate(): void {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row: FriendLink): void {
  isEdit.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleDelete(row: FriendLink): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除友链 "${row.name}" 吗？`, '提示', {
      type: 'warning',
    })
    await deleteFriendLink(row.id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch (error: unknown) {
    if (error === 'cancel' || (error instanceof Error && error.message === 'cancel')) {
      return
    }
    const msg = error instanceof Error ? error.message : '删除失败'
    ElMessage.error(msg)
  }
}

function openLink(url: string): void {
  window.open(url, '_blank', 'noopener,noreferrer')
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    if (isEdit.value && form.value.id) {
      await updateFriendLink(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createFriendLink(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await fetchData()
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : '操作失败'
    ElMessage.error(msg)
  }
}

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-content-primary">友链管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate">
        新建友链
      </el-button>
    </div>

    <el-empty v-if="!loading && links.length === 0" description="暂无友链" />

    <el-table v-if="links.length > 0" v-loading="loading" :data="links" border>
      <el-table-column type="index" label="#" width="50" />
      <el-table-column label="网站" min-width="180">
        <template #default="{ row }">
          <div class="flex items-center gap-3">
            <el-avatar :size="32" :src="row.logo || undefined">
              <el-icon><Link /></el-icon>
            </el-avatar>
            <div class="min-w-0">
              <div class="truncate font-medium text-content-primary">{{ row.name }}</div>
              <div class="truncate text-xs text-content-tertiary">{{ row.description || row.url }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="链接" min-width="220">
        <template #default="{ row }">
          <a :href="row.url" target="_blank" rel="noopener noreferrer" class="text-primary hover:underline">
            {{ row.url }}
          </a>
        </template>
      </el-table-column>
      <el-table-column prop="email" label="邮箱" width="180" />
      <el-table-column prop="sort" label="排序" width="80" align="center" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '显示' : '隐藏' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button :icon="View" size="small" @click="openLink(row.url)" title="访问" />
            <el-button type="primary" :icon="Edit" size="small" @click="handleEdit(row)" title="编辑" />
            <el-button type="danger" :icon="Delete" size="small" @click="handleDelete(row)" title="删除" />
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑友链' : '新建友链'" width="640px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="网站名称" prop="name">
          <el-input v-model="form.name" maxlength="50" show-word-limit placeholder="请输入网站名称" />
        </el-form-item>
        <el-form-item label="网站链接" prop="url">
          <el-input v-model="form.url" placeholder="https://example.com" />
        </el-form-item>
        <el-form-item label="Logo" prop="logo">
          <el-input v-model="form.logo" placeholder="https://example.com/logo.png" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
            placeholder="一句话描述这个站点"
          />
        </el-form-item>
        <el-form-item label="联系邮箱" prop="email">
          <el-input v-model="form.email" placeholder="name@example.com" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="排序" prop="sort">
              <el-input-number v-model="form.sort" :min="0" :max="9999" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-switch
                v-model="form.status"
                :active-value="1"
                :inactive-value="0"
                active-text="显示"
                inactive-text="隐藏"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
