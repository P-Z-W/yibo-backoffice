<script setup lang="ts">
import { CircleCheck } from '@element-plus/icons-vue'

defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>{{ title }}</h1>
      <p>{{ description }}</p>
    </div>
    <ElTag type="success" effect="plain" round>入口已迁移</ElTag>
  </div>

  <section class="surface-card placeholder">
    <div class="placeholder-icon"><CircleCheck /></div>
    <h2>原系统入口已迁移</h2>
    <p>原系统在此模块没有成熟业务功能，新系统已保留同等入口，后续需求可直接在现代架构上迭代。</p>
    <a href="http://127.0.0.1:5001" target="_blank" rel="noreferrer">打开老系统（稳定版）</a>
  </section>
</template>

<style scoped>
.placeholder {
  display: flex;
  min-height: 420px;
  padding: 50px;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  text-align: center;
}

.placeholder-icon {
  display: grid;
  width: 62px;
  height: 62px;
  margin-bottom: 19px;
  place-items: center;
  border-radius: 17px;
  color: #2f6feb;
  background: #eaf1ff;
}

.placeholder-icon svg {
  width: 29px;
}

.placeholder h2 {
  margin: 0 0 10px;
  color: #24314a;
  font-size: 18px;
}

.placeholder p {
  max-width: 520px;
  margin: 0 0 24px;
  color: #8a96a8;
  font-size: 13px;
  line-height: 1.8;
}

.placeholder a {
  color: #2f6feb;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}
</style>
