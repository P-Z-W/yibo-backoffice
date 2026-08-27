<script setup lang="ts">
import { Download, Search } from '@element-plus/icons-vue'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { useRoute } from 'vue-router'
import { getExpressOverview, getExpressStats, type ExpressStats } from '../../api/express'
import { http } from '../../api/http'
import { formatCount } from '../../utils/format'

use([CanvasRenderer, BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent])

const route = useRoute()
const months = ref<string[]>([])
const month = ref('')
const stats = ref<ExpressStats>()
const loading = ref(false)
const previewLoading = ref(false)
const preview = ref<{ rows: Record<string, unknown>[]; total: number; page: number; total_pages: number }>()
const keyword = ref('')

const teamChart = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { top: 15, right: 26, bottom: 28, left: 100 },
  xAxis: { type: 'value', axisLabel: { color: '#8792a5' }, splitLine: { lineStyle: { color: '#edf1f6' } } },
  yAxis: { type: 'category', data: [...(stats.value?.team_stats.slice(0, 10) ?? [])].reverse().map((item) => item.team), axisLabel: { color: '#66748a', width: 85, overflow: 'truncate' } },
  series: [{ type: 'bar', data: [...(stats.value?.team_stats.slice(0, 10) ?? [])].reverse().map((item) => item.amount), barWidth: 12, itemStyle: { color: '#2f6feb', borderRadius: [0, 5, 5, 0] } }],
}))

const expressChart = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, textStyle: { color: '#78859a', fontSize: 11 } },
  series: [{ type: 'pie', radius: ['46%', '70%'], center: ['50%', '43%'], label: { show: false }, data: stats.value?.express_stats.map((item) => ({ name: item.name, value: item.amount })) ?? [], itemStyle: { borderColor: '#fff', borderWidth: 3 } }],
}))

async function loadStats() {
  if (!month.value) return
  loading.value = true
  preview.value = undefined
  try { stats.value = await getExpressStats(month.value) } finally { loading.value = false }
}

async function loadPreview(page = 1) {
  previewLoading.value = true
  try {
    preview.value = (await http.get(`/express/preview/${month.value}`, { params: { page, size: 50, keyword: keyword.value } })).data
  } finally { previewLoading.value = false }
}

onMounted(async () => {
  const overview = await getExpressOverview()
  months.value = overview.months
  const requested = typeof route.query.month === 'string' ? route.query.month : ''
  month.value = months.value.includes(requested) ? requested : overview.selected_month
})
watch(month, loadStats)
</script>

<template>
  <div class="page-heading">
    <div><h1>快递统计</h1><p>客户费用、快递占比、异常运单和账单明细。</p></div>
    <ElSelect v-model="month" style="width:150px"><ElOption v-for="item in months" :key="item" :label="item" :value="item" /></ElSelect>
  </div>

  <div v-loading="loading">
    <section class="metric-grid">
      <article class="surface-card"><span>运单总量</span><strong>{{ formatCount(stats?.total_orders) }}</strong></article>
      <article class="surface-card"><span>已匹配</span><strong>{{ formatCount(stats?.matched_orders) }}</strong></article>
      <article class="surface-card"><span>未匹配</span><strong>{{ formatCount(stats?.unmatched_orders) }}</strong></article>
      <article class="surface-card"><span>应付金额</span><strong>¥ {{ formatCount(stats?.total_amount) }}</strong></article>
    </section>

    <div class="chart-grid">
      <section class="surface-card chart-card"><h3>客户费用 TOP 10</h3><VChart :option="teamChart" autoresize class="chart" /></section>
      <section class="surface-card chart-card"><h3>快递费用占比</h3><VChart :option="expressChart" autoresize class="chart" /></section>
    </div>

    <section class="surface-card anomaly-card">
      <div class="card-title-row"><div><h3>异常分析</h3><p>沿用老系统的重量、省份、金额和团队匹配规则。</p></div><ElButton tag="a" :href="`/api/v1/express/anomalies/${month}/download`" :icon="Download">导出异常</ElButton></div>
      <ElTable :data="stats?.anomalies ?? []" stripe>
        <ElTableColumn prop="type" label="异常类型" min-width="150" />
        <ElTableColumn label="级别" width="100"><template #default="{ row }"><ElTag :type="row.level === 'high' ? 'danger' : 'warning'" effect="light">{{ row.level === 'high' ? '高' : '中' }}</ElTag></template></ElTableColumn>
        <ElTableColumn prop="count" label="数量" width="110" />
        <ElTableColumn label="占比" width="100"><template #default="{ row }">{{ row.pct }}%</template></ElTableColumn>
        <ElTableColumn label="示例运单"><template #default="{ row }">{{ row.samples.join('、') || '—' }}</template></ElTableColumn>
      </ElTable>
    </section>

    <section class="surface-card preview-card">
      <div class="card-title-row"><div><h3>对账明细</h3><p>按需加载，支持运单号、团队、省份和快递搜索。</p></div><div class="search-box"><ElInput v-model="keyword" placeholder="搜索明细" :prefix-icon="Search" clearable @keyup.enter="loadPreview(1)" /><ElButton type="primary" @click="loadPreview(1)">加载明细</ElButton></div></div>
      <ElTable v-if="preview" v-loading="previewLoading" :data="preview.rows" height="430" stripe>
        <ElTableColumn v-for="column in Object.keys(preview.rows[0] ?? {})" :key="column" :prop="column" :label="column" min-width="130" show-overflow-tooltip />
      </ElTable>
      <ElEmpty v-else description="点击“加载明细”查看迁移的完整对账数据" />
      <ElPagination v-if="preview" v-model:current-page="preview.page" layout="prev, pager, next, total" :total="preview.total" :page-size="50" @current-change="loadPreview" />
    </section>
  </div>
</template>

<style scoped>
.metric-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:17px; margin-bottom:18px; }
.metric-grid article { padding:22px; }
.metric-grid span { color:#7d899b; font-size:12px; }
.metric-grid strong { display:block; margin-top:10px; color:#172641; font-size:24px; }
.chart-grid { display:grid; grid-template-columns:1.4fr .8fr; gap:18px; margin-bottom:18px; }
.chart-card,.anomaly-card,.preview-card { padding:24px 26px; }
h3 { margin:0; color:#243149; font-size:16px; }
.chart { height:330px; }
.anomaly-card,.preview-card { margin-bottom:18px; }
.card-title-row { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:18px; gap:18px; }
.card-title-row p { margin:6px 0 0; color:#929dad; font-size:11px; }
.search-box { display:flex; gap:8px; width:380px; }
.preview-card :deep(.el-pagination) { justify-content:flex-end; margin-top:18px; }
@media(max-width:1000px){.metric-grid{grid-template-columns:repeat(2,1fr)}.chart-grid{grid-template-columns:1fr}}
</style>
