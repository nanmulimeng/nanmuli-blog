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
const tableRef = ref()

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
  color: [
    { required: true, message: '请选择颜色', trigger: 'change' },
    { pattern: /^#[0-9A-Fa-f]{6}$/, message: '颜色格式不正确', trigger: 'change' }
  ]
}

// 预定义常用颜色
const predefineColors = [
  '#409EFF', // 蓝色
  '#67C23A', // 绿色
  '#E6A23C', // 黄色
  '#F56C6C', // 红色
  '#909399', // 灰色
  '#FF6B6B', // 珊瑚红
  '#4ECDC4', // 青绿色
  '#45B7D1', // 天蓝色
  '#96CEB4', // 薄荷绿
  '#FFEAA7', // 淡黄色
  '#DDA0DD', // 梅花色
  '#98D8C8'  // 浅青色
]

// 颜色变化处理 - 确保格式正确
function handleColorChange(color: string | null) {
  if (!color || color === '') {
    form.value.color = '#409EFF'
  }
}

// 计算当前编辑项是否有子分类
const hasChildren = computed(() => {
  if (!isEdit.value || !form.value.id) return false
  return categoryTree.value.some(c => c.parentId === form.value.id) ||
         flatCategories.value.some(c => c.parentId === form.value.id)
})

// 计算可选的父分类（排除自身及子分类，避免循环引用）
const parentOptions = computed(() => {
  if (!isEdit.value || !form.value.id) {
    // 新建模式：只能选非叶子分类
    return flatCategories.value.filter(c => !c.isLeaf)
  }
  // 编辑模式：排除自身及所有子分类
  const descendantIds = getAllDescendantIds(categoryTree.value, form.value.id)
  return flatCategories.value.filter(c =>
    !c.isLeaf && // 必须是父分类
    !descendantIds.has(c.id) // 不能是自身或子分类
  )
})

// 递归获取所有分类（不修改原始数据）
function flattenCategories(categories: Category[]): Category[] {
  const result: Category[] = []
  function traverse(list: Category[]) {
    list.forEach(item => {
      // 创建新对象避免污染原始数据，不再添加缩进（树形表格自带缩进）
      result.push({ ...item })
      if (item.children?.length) {
        traverse(item.children)
      }
    })
  }
  traverse(categories)
  return result
}

// 递归获取指定分类的所有子分类ID（用于循环引用检测）
function getAllDescendantIds(categories: Category[], parentId: string): Set<string> {
  const ids = new Set<string>([parentId])
  function traverse(list: Category[]) {
    list.forEach(item => {
      if (item.parentId === parentId || ids.has(item.parentId || '')) {
        ids.add(item.id)
        if (item.children?.length) {
          traverse(item.children)
        }
      }
    })
  }
  traverse(categories)
  return ids
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

function handleCreate(parentId?: string) {
  isEdit.value = false
  // 如果指定了父分类，根据父分类类型设置默认值
  const parentCategory = parentId ? flatCategories.value.find(c => c.id === parentId) : null
  form.value = {
    name: '',
    slug: '',
    description: '',
    icon: parentCategory?.icon || '',
    color: parentCategory?.color || '#409EFF',
    sort: 0,
    parentId: parentId || null,
    // 子分类默认设为叶子分类（但如果父分类是叶子则不能创建子分类，这里主要是后端控制）
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
  // 检查是否有子分类（前端预检）
  const hasChildCategories = categoryTree.value.some(c => c.parentId === row.id) ||
                              flatCategories.value.some(c => c.parentId === row.id)
  if (hasChildCategories) {
    ElMessage.warning('该分类下有子分类，请先删除子分类')
    return
  }

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
    } else if (error?.message && error.message !== 'cancel') {
      ElMessage.error(error.message)
    }
    // 取消删除不处理
  }
}

async function handleSubmit() {
  if (!formRef.value) return

  // 确保颜色字段有有效值
  if (!form.value.color || form.value.color === '') {
    form.value.color = '#409EFF'
  }

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
      // 显示后端返回的具体错误信息
      const message = error?.response?.data?.message || error?.message || '操作失败'
      ElMessage.error(message)
    }
  })
}

// 使用 el-table 的 tree-props 实现树形展示
const tableData = computed(() => categoryTree.value)

// 切换行展开/折叠
function toggleRowExpansion(row: Category) {
  if (row.children && row.children.length > 0) {
    tableRef.value?.toggleRowExpansion(row)
  }
}

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

    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="tableData"
      border
      row-key="id"
      :tree-props="{ children: 'children' }"
      default-expand-all
      class="category-table"
      :indent="32"
    >
      <el-table-column label="分类名称" min-width="200" class-name="category-name-cell">
        <template #default="{ row }">
          <div
            class="flex items-center category-name-wrapper"
            :class="{ 'cursor-pointer': row.children?.length > 0, 'hover:text-primary': row.children?.length > 0 }"
            @click="toggleRowExpansion(row)"
          >
            <el-icon v-if="!row.isLeaf" class="mr-2 text-yellow-500">
              <Folder />
            </el-icon>
            <el-icon v-else class="mr-2 text-blue-500">
              <Document />
            </el-icon>
            <span class="category-name-text">{{ row.name }}</span>
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

      <el-table-column label="操作" width="180" fixed="right" align="center">
        <template #default="{ row }">
          <el-button-group>
            <el-button
              v-if="!row.isLeaf"
              type="primary"
              :icon="Plus"
              size="small"
              @click="handleCreate(row.id)"
              title="添加子类"
            />
            <el-button type="primary" :icon="Edit" size="small" @click="handleEdit(row)" title="编辑" />
            <el-button type="danger" :icon="Delete" size="small" @click="handleDelete(row)" title="删除" />
          </el-button-group>
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
          <div v-if="isEdit && form.id" class="text-xs text-gray-500 mt-1">
            提示：自身及子分类不可选，避免循环引用
          </div>
        </el-form-item>

        <el-form-item label="分类名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入分类名称" />
        </el-form-item>

        <el-form-item label="分类标识" prop="slug">
          <el-input v-model="form.slug" placeholder="用于URL，如：java" />
        </el-form-item>

        <el-form-item label="类型">
          <el-radio-group v-model="form.isLeaf" :disabled="hasChildren">
            <el-radio :value="false">父分类（容器）</el-radio>
            <el-radio :value="true">叶子分类（可关联文章）</el-radio>
          </el-radio-group>
          <div v-if="hasChildren" class="text-xs text-amber-600 mt-1">
            该分类下有子分类，不能修改为叶子分类
          </div>
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

        <el-form-item label="颜色" prop="color">
          <div class="flex items-center gap-3">
            <el-color-picker
              v-model="form.color"
              :predefine="predefineColors"
              @change="handleColorChange"
            />
            <span class="text-xs text-gray-500">{{ form.color || '未设置' }}</span>
          </div>
        </el-form-item>

        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>

        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">禁用</el-radio>
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

<style scoped>
/* 分类名称可点击展开 */
.category-name-wrapper {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.category-name-wrapper.cursor-pointer:hover {
  background-color: var(--el-fill-color-light);
  color: var(--el-color-primary);
}

.category-name-wrapper .category-name-text {
  font-weight: 500;
}

/* 展开图标默认大小 */
.category-table :deep(.el-table__expand-icon) {
  margin-right: 4px;
}

/* 操作按钮组样式优化 */
.category-table :deep(.el-button-group .el-button) {
  padding: 6px 10px;
}

/* 操作列居中 */
.category-table :deep(.el-table__cell:last-child .cell) {
  display: flex;
  justify-content: center;
}
</style>
