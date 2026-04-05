<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Folder, Document } from '@element-plus/icons-vue'
import { getAdminCategoryList, createCategory, updateCategory, deleteCategory } from '@/api/category'
import type { Category } from '@/types/category'

const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const categoryTree = ref<Category[]>([])
const flatCategories = ref<Category[]>([])

const form = ref<Partial<Category>>({
  name: '',
  slug: '',
  description: '',
  icon: '',
  color: '#409EFF',
  sort: 0,
  parentId: null,
  isLeaf: true,
  status: 1,
})

const formRef = ref()

const rules = {
  name: [{ required: true, message: '请输入分类名称', trigger: 'blur' }],
  slug: [{ required: true, message: '请输入分类标识', trigger: 'blur' }],
}

// 计算可选的父分类（只能是父分类，不能是叶子分类）
const parentOptions = computed(() => {
  return flatCategories.value.filter(c => !c.isLeaf)
})

// 递归获取所有分类
function flattenCategories(categories: Category[]): Category[] {
  const result: Category[] = []
  function traverse(list: Category[], depth = 0) {
    list.forEach(item => {
      result.push({ ...item, name: '  '.repeat(depth) + item.name })
      if (item.children?.length) {
        traverse(item.children, depth + 1)
      }
    })
  }
  traverse(categories)
  return result
}

async function fetchData() {
  loading.value = true
  try {
    categoryTree.value = await getAdminCategoryList()
    flatCategories.value = flattenCategories(categoryTree.value)
  } catch {
    ElMessage.error('加载分类失败')
  } finally {
    loading.value = false
  }
}

function handleCreate(parentId?: number) {
  isEdit.value = false
  form.value = {
    name: '',
    slug: '',
    description: '',
    icon: '',
    color: '#409EFF',
    sort: 0,
    parentId: parentId || null,
    isLeaf: true,
    status: 1,
  }
  dialogVisible.value = true
}

function handleEdit(row: Category) {
  isEdit.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleDelete(row: Category) {
  try {
    await ElMessageBox.confirm(
      `确定要删除分类 "${row.name}" 吗？`,
      '警告',
      { type: 'warning' }
    )
    await deleteCategory(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error: any) {
    // 如果后端返回错误，显示错误信息
    if (error?.response?.data?.message) {
      ElMessage.error(error.response.data.message)
    }
    // 取消删除不处理
  }
}

async function handleSubmit() {
  if (!formRef.value) return

  await formRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    try {
      if (isEdit.value && form.value.id) {
        await updateCategory(form.value.id, form.value)
        ElMessage.success('更新成功')
      } else {
        await createCategory(form.value)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } catch (error: any) {
      ElMessage.error(error?.message || '操作失败')
    }
  })
}

// 递归渲染树形表格
function renderTreeTable(data: Category[], depth = 0): any[] {
  const result: any[] = []
  data.forEach(item => {
    result.push({ ...item, depth })
    if (item.children?.length) {
      result.push(...renderTreeTable(item.children, depth + 1))
    }
  })
  return result
}

const tableData = computed(() => renderTreeTable(categoryTree.value))

onMounted(fetchData)
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h2 class="text-xl font-bold text-gray-900">分类管理</h2>
      <el-button type="primary" :icon="Plus" @click="handleCreate()">
        新建根分类
      </el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      class="mb-4"
    >
      <template #title>
        <div class="flex items-center gap-2">
          <el-icon><Folder /></el-icon>
          <span>父分类（文件夹图标）：作为容器，不能直接关联文章</span>
        </div>
        <div class="mt-1 flex items-center gap-2">
          <el-icon><Document /></el-icon>
          <span>叶子分类（文档图标）：可关联文章，相当于原标签概念</span>
        </div>
      </template>
    </el-alert>

    <el-table v-loading="loading" :data="tableData" border row-key="id">
      <el-table-column label="分类名称" min-width="200">
        <template #default="{ row }">
          <div class="flex items-center" :style="{ paddingLeft: row.depth * 20 + 'px' }">
            <el-icon v-if="!row.isLeaf" class="mr-2 text-yellow-500">
              <Folder />
            </el-icon>
            <el-icon v-else class="mr-2 text-blue-500">
              <Document />
            </el-icon>
            <span>{{ row.name }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="slug" label="标识" width="120" />

      <el-table-column label="类型" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.isLeaf" type="success" size="small">叶子</el-tag>
          <el-tag v-else type="warning" size="small">父分类</el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="articleCount" label="文章数" width="80" />

      <el-table-column prop="sort" label="排序" width="80" />

      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.status === 1" type="success" size="small">启用</el-tag>
          <el-tag v-else type="info" size="small">禁用</el-tag>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="!row.isLeaf"
            type="primary"
            link
            :icon="Plus"
            @click="handleCreate(row.id)"
          >
            添加子类
          </el-button>
          <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">
            编辑
          </el-button>
          <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑/创建弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑分类' : '创建分类'"
      width="600px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="父分类">
          <el-select v-model="form.parentId" clearable placeholder="无（作为根分类）" class="w-full">
            <el-option
              v-for="item in parentOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="分类名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入分类名称" />
        </el-form-item>

        <el-form-item label="分类标识" prop="slug">
          <el-input v-model="form.slug" placeholder="用于URL，如：java" />
        </el-form-item>

        <el-form-item label="类型">
          <el-radio-group v-model="form.isLeaf">
            <el-radio :label="false">父分类（容器）</el-radio>
            <el-radio :label="true">叶子分类（可关联文章）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="分类描述"
          />
        </el-form-item>

        <el-form-item label="图标">
          <el-input v-model="form.icon" placeholder="Element Plus 图标名称" />
        </el-form-item>

        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" />
        </el-form-item>

        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>

        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :label="1">启用</el-radio>
            <el-radio :label="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
