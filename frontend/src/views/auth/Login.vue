<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/modules/user'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const loading = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应为3-20个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 32, message: '密码长度应为6-32个字符', trigger: 'blur' }
  ],
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.loginAction({
      username: form.username,
      password: form.password,
    })
    ElMessage.success('登录成功')
    // 支持重定向：优先跳转到 redirect 参数指定的页面，否则默认到 /admin
    const redirect = route.query.redirect as string
    await router.push(redirect || '/admin')
  } catch (error: any) {
    ElMessage.error(error?.message || '登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-surface-primary p-4">
    <div class="w-full max-w-md rounded-2xl bg-surface-secondary p-8 shadow-xl border border-border">
      <div class="mb-8 text-center">
        <h1 class="text-2xl font-bold text-content-primary">管理员登录</h1>
        <p class="mt-2 text-sm text-content-secondary">个人技术博客管理后台</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            :prefix-icon="User"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleSubmit"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          class="w-full"
          :loading="loading"
          @click="handleSubmit"
        >
          登录
        </el-button>
      </el-form>

      <div class="mt-6 text-center">
        <router-link to="/" class="text-sm text-primary hover:underline">
          返回首页
        </router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 暗色模式输入框样式适配 */
:deep(.el-input__wrapper) {
  background-color: var(--theme-bg-tertiary);
  box-shadow: 0 0 0 1px var(--theme-border) inset;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--theme-primary) inset;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--theme-primary) inset;
}

:deep(.el-input__inner) {
  color: var(--theme-text-primary);
  background-color: transparent;
}

:deep(.el-input__inner::placeholder) {
  color: var(--theme-text-tertiary);
}

:deep(.el-form-item__label) {
  color: var(--theme-text-secondary);
}
</style>
