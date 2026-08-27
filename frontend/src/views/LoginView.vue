<script setup lang="ts">
import { Lock, Right, User } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive({ username: 'admin', password: '' })
const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await auth.login(form.username.trim(), form.password)
    const target = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(target)
  } catch {
    ElMessage.error('用户名或密码不正确')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <section class="login-story">
      <div class="story-glow"></div>
      <div class="story-content">
        <div class="story-brand">
          <span class="brand-symbol">YB</span>
          <span>毅播云仓</span>
        </div>
        <div class="version-chip">NEW SYSTEM · V1.0</div>
        <h1>让经营数据，<br />成为每天的决策依据。</h1>
        <p>统一指标、业务事件和月度复盘，从这套新系统开始逐步沉淀。</p>
        <div class="story-points">
          <div><span>01</span>独立的新系统与新数据库</div>
          <div><span>02</span>经营分析优先建设</div>
          <div><span>03</span>成熟模块稳步迁移</div>
        </div>
      </div>
      <div class="story-footer">YIBO OPERATIONS PLATFORM</div>
    </section>

    <section class="login-panel">
      <div class="login-card">
        <div class="login-heading">
          <span class="eyebrow">欢迎回来</span>
          <h2>登录新管理系统</h2>
          <p>当前为第一版，使用原管理员账号进入。</p>
        </div>

        <ElForm ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
          <ElFormItem label="用户名" prop="username">
            <ElInput v-model="form.username" :prefix-icon="User" size="large" autocomplete="username" />
          </ElFormItem>
          <ElFormItem label="密码" prop="password">
            <ElInput
              v-model="form.password"
              :prefix-icon="Lock"
              type="password"
              size="large"
              show-password
              autocomplete="current-password"
            />
          </ElFormItem>
          <ElButton type="primary" size="large" :loading="submitting" class="submit-button" @click="submit">
            进入系统
            <ElIcon class="el-icon--right"><Right /></ElIcon>
          </ElButton>
        </ElForm>

        <div class="legacy-link">
          老系统继续承载成熟业务
          <a href="http://127.0.0.1:5001" target="_blank" rel="noreferrer">打开稳定版</a>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  grid-template-columns: minmax(460px, 1.08fr) minmax(440px, 0.92fr);
  background: #fff;
}

.login-story {
  position: relative;
  display: flex;
  min-height: 100vh;
  padding: 54px clamp(46px, 7vw, 110px) 38px;
  overflow: hidden;
  flex-direction: column;
  justify-content: space-between;
  color: #fff;
  background:
    linear-gradient(rgba(9, 28, 57, 0.3) 1px, transparent 1px),
    linear-gradient(90deg, rgba(9, 28, 57, 0.3) 1px, transparent 1px),
    linear-gradient(145deg, #102b55 0%, #0b1d39 68%, #071629 100%);
  background-size: 48px 48px, 48px 48px, auto;
}

.story-glow {
  position: absolute;
  top: 16%;
  right: -16%;
  width: 520px;
  height: 520px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(42, 120, 235, 0.42), rgba(20, 90, 195, 0.03) 66%, transparent 70%);
}

.story-content,
.story-footer {
  position: relative;
  z-index: 1;
}

.story-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.brand-symbol {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 12px;
  background: linear-gradient(145deg, #4389f5, #1f5cc4);
  box-shadow: 0 12px 30px rgba(24, 98, 211, 0.4);
  font-size: 13px;
  letter-spacing: 0.04em;
}

.version-chip {
  display: inline-block;
  margin-top: clamp(70px, 12vh, 135px);
  padding: 6px 10px;
  border: 1px solid rgba(105, 205, 218, 0.25);
  border-radius: 7px;
  color: #72d1de;
  background: rgba(35, 162, 182, 0.1);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.login-story h1 {
  margin: 22px 0 20px;
  font-size: clamp(38px, 4vw, 58px);
  line-height: 1.2;
  letter-spacing: -0.04em;
}

.login-story p {
  max-width: 510px;
  margin: 0;
  color: #aabbd2;
  font-size: 16px;
  line-height: 1.9;
}

.story-points {
  display: grid;
  max-width: 550px;
  margin-top: 50px;
  gap: 15px;
  grid-template-columns: repeat(3, 1fr);
  color: #bdc9da;
  font-size: 12px;
  line-height: 1.6;
}

.story-points div {
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
}

.story-points span {
  display: block;
  margin-bottom: 4px;
  color: #4b8ff0;
  font-size: 10px;
  font-weight: 700;
}

.story-footer {
  color: #536b8e;
  font-size: 10px;
  letter-spacing: 0.18em;
}

.login-panel {
  display: grid;
  min-height: 100vh;
  padding: 50px;
  place-items: center;
  background: #fff;
}

.login-card {
  width: min(100%, 420px);
}

.login-heading {
  margin-bottom: 34px;
}

.eyebrow {
  color: #2f6feb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.login-heading h2 {
  margin: 10px 0 9px;
  color: #14223c;
  font-size: 30px;
  letter-spacing: -0.02em;
}

.login-heading p {
  margin: 0;
  color: #8894a7;
  font-size: 13px;
}

.login-card :deep(.el-form-item) {
  margin-bottom: 24px;
}

.login-card :deep(.el-form-item__label) {
  color: #4a566b;
  font-weight: 600;
}

.login-card :deep(.el-input__wrapper) {
  height: 48px;
  border-radius: 9px;
  box-shadow: 0 0 0 1px #dfe5ee inset;
}

.login-card :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #2f6feb inset, 0 0 0 4px rgba(47, 111, 235, 0.08);
}

.submit-button {
  width: 100%;
  height: 49px;
  margin-top: 3px;
  border-radius: 9px;
  background: linear-gradient(90deg, #2f6feb, #245bc2);
  box-shadow: 0 10px 24px rgba(47, 111, 235, 0.22);
  font-weight: 600;
}

.legacy-link {
  display: flex;
  justify-content: space-between;
  margin-top: 31px;
  padding-top: 21px;
  border-top: 1px solid #edf0f5;
  color: #95a0b1;
  font-size: 12px;
}

.legacy-link a {
  color: #2f6feb;
  font-weight: 600;
  text-decoration: none;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .login-story {
    display: none;
  }

  .login-panel {
    padding: 30px;
  }
}
</style>
