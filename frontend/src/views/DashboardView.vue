<script setup lang="ts">
import { CircleCheck, Clock, Connection, DataAnalysis, Right } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { http } from '../api/http'

interface Overview {
  version: string
  database: string
  modules: Array<{ name: string; status: 'ready' }>
  analytics: {
    metric_definitions: number
    metric_values: number
    monthly_reviews: number
  }
}

const router = useRouter()
const overview = ref<Overview>()
const loading = ref(true)
const loadFailed = ref(false)

onMounted(async () => {
  try {
    const { data } = await http.get<Overview>('/system/overview')
    overview.value = data
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>工作台</h1>
      <p>新系统迁移总览。成熟业务、历史数据和文件均已独立迁入。</p>
    </div>
    <ElTag type="primary" effect="light" round>新系统 {{ overview?.version ?? '1.0.0' }}</ElTag>
  </div>

  <ElAlert v-if="loadFailed" title="暂时无法读取系统状态，请确认后端服务已启动。" type="warning" :closable="false" />

  <div v-loading="loading" class="status-grid">
    <article class="surface-card hero-card">
      <div class="hero-icon"><DataAnalysis /></div>
      <div class="hero-copy">
        <span>新版经营中心</span>
        <h2>经营分析</h2>
        <p>月度复盘已升级为可追溯、可录入、可分析的经营数据中心。</p>
      </div>
      <ElButton type="primary" :icon="Right" @click="router.push('/analytics')">进入模块</ElButton>
    </article>

    <article class="surface-card stat-card">
      <span class="stat-label">新数据库</span>
      <strong>{{ overview?.database ?? 'yibo_backoffice' }}</strong>
      <p><CircleCheck /> 与老系统完全隔离</p>
    </article>

    <article class="surface-card stat-card">
      <span class="stat-label">指标定义</span>
      <strong>{{ overview?.analytics.metric_definitions ?? 0 }}</strong>
      <p><Connection /> 经营指标已迁入</p>
    </article>

    <article class="surface-card stat-card">
      <span class="stat-label">月度复盘</span>
      <strong>{{ overview?.analytics.monthly_reviews ?? 0 }}</strong>
      <p><Clock /> 按月持续复盘</p>
    </article>
  </div>

  <section class="surface-card roadmap">
    <div class="section-heading">
      <div>
        <h3>模块迁移状态</h3>
        <p>新老系统数据库与文件独立，老系统仍可作为稳定备份运行。</p>
      </div>
      <span>V1.0</span>
    </div>

    <div class="module-list">
      <div v-for="(module, index) in overview?.modules ?? []" :key="module.name" class="module-row">
        <div class="module-index">{{ String(index + 1).padStart(2, '0') }}</div>
        <div class="module-copy">
          <strong>{{ module.name }}</strong>
          <span>业务功能已迁入新架构</span>
        </div>
        <ElTag type="success" effect="plain" round>已迁移</ElTag>
      </div>
    </div>
  </section>
</template>

<style scoped>
.status-grid {
  display: grid;
  margin-bottom: 22px;
  gap: 18px;
  grid-template-columns: minmax(340px, 1.65fr) repeat(3, minmax(180px, 0.72fr));
}

.hero-card {
  display: flex;
  min-height: 178px;
  padding: 27px;
  align-items: center;
  gap: 18px;
  color: #fff;
  border: 0;
  background:
    radial-gradient(circle at 78% 10%, rgba(83, 156, 255, 0.32), transparent 35%),
    linear-gradient(135deg, #173b75, #102b55);
}

.hero-icon {
  display: grid;
  width: 56px;
  height: 56px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.09);
}

.hero-icon svg {
  width: 29px;
}

.hero-copy {
  min-width: 0;
  flex: 1;
}

.hero-copy span {
  color: #83b0f2;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.hero-copy h2 {
  margin: 6px 0 5px;
  font-size: 25px;
}

.hero-copy p {
  max-width: 420px;
  margin: 0;
  color: #b9c9df;
  font-size: 12px;
  line-height: 1.7;
}

.stat-card {
  display: flex;
  min-height: 178px;
  padding: 24px;
  flex-direction: column;
  justify-content: center;
}

.stat-label {
  color: #778399;
  font-size: 12px;
}

.stat-card strong {
  margin: 12px 0 15px;
  overflow: hidden;
  color: #172641;
  font-size: 24px;
  text-overflow: ellipsis;
}

.stat-card p {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0;
  color: #8d98a9;
  font-size: 11px;
}

.stat-card p svg {
  width: 15px;
  color: #21a3b8;
}

.roadmap {
  padding: 27px 29px;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 21px;
  border-bottom: 1px solid #edf0f5;
}

.section-heading h3 {
  margin: 0 0 6px;
  color: #1c2941;
  font-size: 17px;
}

.section-heading p {
  margin: 0;
  color: #8b96a8;
  font-size: 12px;
}

.section-heading > span {
  color: #9ba5b5;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.module-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(280px, 1fr));
}

.module-row {
  display: flex;
  min-height: 90px;
  padding: 20px 14px;
  align-items: center;
  gap: 14px;
  border-bottom: 1px solid #f0f2f6;
}

.module-row:nth-child(odd) {
  padding-right: 28px;
  border-right: 1px solid #f0f2f6;
}

.module-row:nth-child(even) {
  padding-left: 28px;
}

.module-index {
  color: #a9b2c0;
  font-size: 11px;
  font-weight: 700;
}

.module-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.module-copy strong {
  color: #27344b;
  font-size: 14px;
}

.module-copy span {
  margin-top: 5px;
  color: #929dac;
  font-size: 11px;
}

@media (max-width: 1280px) {
  .status-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .hero-card {
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .status-grid,
  .module-list {
    grid-template-columns: 1fr;
  }

  .module-row:nth-child(odd),
  .module-row:nth-child(even) {
    padding-right: 14px;
    padding-left: 14px;
    border-right: 0;
  }
}
</style>
