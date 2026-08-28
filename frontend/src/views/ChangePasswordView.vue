<script setup lang="ts">
import { Key, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const form = reactive({ current: '', password: '', confirm: '' })

async function submit() {
  if (form.password.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (form.password !== form.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  loading.value = true
  try {
    await auth.changePassword(form.current, form.password)
    ElMessage.success('密码修改成功')
    await router.replace('/')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '密码修改失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="password-page">
    <section class="password-card">
      <div class="brand-icon"><Lock /></div>
      <span class="eyebrow">账号安全</span>
      <h1>{{ auth.mustChangePassword ? '请修改默认密码' : '修改登录密码' }}</h1>
      <p>新密码至少 6 位，不限制字符组合。</p>
      <ElForm label-position="top" @submit.prevent="submit">
        <ElFormItem label="当前密码">
          <ElInput v-model="form.current" type="password" show-password autocomplete="current-password" />
        </ElFormItem>
        <ElFormItem label="新密码">
          <ElInput v-model="form.password" type="password" show-password autocomplete="new-password" />
        </ElFormItem>
        <ElFormItem label="确认新密码">
          <ElInput v-model="form.confirm" type="password" show-password autocomplete="new-password" />
        </ElFormItem>
        <ElButton type="primary" :icon="Key" :loading="loading" native-type="submit">保存并进入系统</ElButton>
      </ElForm>
    </section>
  </div>
</template>

<style scoped>
.password-page { display:grid; min-height:100vh; padding:30px; place-items:center; background:radial-gradient(circle at 15% 15%, #e7f0ff, transparent 30%), #f3f6fb; }
.password-card { width:min(460px, 100%); padding:42px; border:1px solid #e2e8f2; border-radius:22px; background:#fff; box-shadow:0 24px 70px rgba(20,49,91,.12); }
.brand-icon { display:grid; width:52px; height:52px; margin-bottom:24px; place-items:center; border-radius:16px; color:#fff; background:linear-gradient(145deg,#3b82f6,#1e5fc4); }
.brand-icon :deep(svg) { width:25px; }
.eyebrow { color:#2f6feb; font-size:12px; font-weight:700; letter-spacing:.12em; }
h1 { margin:9px 0; color:#16223a; font-size:25px; }
p { margin:0 0 28px; color:#7b8799; font-size:14px; }
.el-button { width:100%; margin-top:6px; }
</style>
