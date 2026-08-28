<script setup lang="ts">
import { Lock } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="state-page">
    <div class="state-icon"><Lock /></div>
    <h1>当前账号无权访问</h1>
    <p>如需使用该功能，请联系系统管理员调整角色权限。</p>
    <ElButton type="primary" @click="router.push('/')">返回工作台</ElButton>
  </div>
</template>

<style scoped>
.state-page { display:grid; min-height:calc(100vh - 170px); place-content:center; justify-items:center; text-align:center; }
.state-icon { display:grid; width:68px; height:68px; place-items:center; border-radius:22px; color:#2f6feb; background:#eaf1ff; }
.state-icon :deep(svg) { width:30px; }
h1 { margin:22px 0 9px; font-size:24px; }
p { margin:0 0 24px; color:#78859a; }
</style>
