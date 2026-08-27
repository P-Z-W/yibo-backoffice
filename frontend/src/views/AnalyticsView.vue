<script setup lang="ts">
import { Check, EditPen, Refresh, TrendCharts } from '@element-plus/icons-vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { getAnalytics, saveAnalytics, type AnalyticsData, type AnalyticsMetric } from '../api/analytics'
import { formatCount } from '../utils/format'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const selectedMonth = ref('2026-07')
const data = ref<AnalyticsData>()
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const editValues = ref<Record<number, number | null>>({})
const editNotes = ref<Record<number, string>>({})
const summary = ref('')

const categoryOrder = ['发货', '退货', '客户', '供应商', '人员场地', '其他']
const groupedMetrics = computed(() => categoryOrder
  .map((category) => ({ category, metrics: data.value?.metrics.filter((metric) => metric.category === category) ?? [] }))
  .filter((group) => group.metrics.length))

function metricByCode(code: string) {
  return data.value?.metrics.find((metric) => metric.code === code)
}

const headlineMetrics = computed(() => [
  { label: '发货单量', metric: metricByCode('shipping_orders'), tone: 'blue' },
  { label: '退货件数', metric: metricByCode('return_items'), tone: 'cyan' },
  { label: '新进客户', metric: metricByCode('new_customers'), tone: 'purple' },
  { label: '人员规模', metric: metricByCode('staff_adjustment'), tone: 'orange' },
])

const trendOption = computed(() => {
  const shipping = data.value?.trend.shipping_orders ?? []
  const returns = data.value?.trend.return_items ?? []
  const months = Array.from(new Set([...shipping.map((item) => item.month), ...returns.map((item) => item.month)])).sort()
  const values = (rows: Array<{ month: string; value: number }>) => {
    const map = new Map(rows.map((item) => [item.month, item.value]))
    return months.map((month) => map.get(month) ?? null)
  }
  return {
    animation: false,
    grid: { top: 48, right: 24, bottom: 34, left: 58 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 0, data: ['发货单量', '退货件数'] },
    xAxis: { type: 'category', boundaryGap: false, data: months, axisLabel: { color: '#8793a5' } },
    yAxis: { type: 'value', axisLabel: { color: '#8793a5' }, splitLine: { lineStyle: { color: '#edf1f6' } } },
    series: [
      { name: '发货单量', type: 'line', smooth: true, data: values(shipping), lineStyle: { color: '#2f6feb', width: 2 }, itemStyle: { color: '#2f6feb' }, areaStyle: { color: 'rgba(47,111,235,.08)' } },
      { name: '退货件数', type: 'line', smooth: true, data: values(returns), lineStyle: { color: '#21a3b8', width: 2 }, itemStyle: { color: '#21a3b8' } },
    ],
  }
})

function displayValue(metric?: AnalyticsMetric) {
  if (!metric || metric.value === null) return '—'
  return metric.precision ? metric.value.toFixed(metric.precision) : formatCount(metric.value)
}

function changeType(metric: AnalyticsMetric) {
  if (metric.change === null || metric.change === 0) return 'info'
  return metric.change > 0 ? 'success' : 'danger'
}

function resetEditor() {
  editValues.value = Object.fromEntries((data.value?.metrics ?? []).map((metric) => [metric.id, metric.value]))
  editNotes.value = Object.fromEntries((data.value?.metrics ?? []).map((metric) => [metric.id, metric.note]))
  summary.value = data.value?.review.summary ?? ''
}

async function load() {
  loading.value = true
  try {
    data.value = await getAnalytics(selectedMonth.value)
    resetEditor()
    editing.value = false
  } finally {
    loading.value = false
  }
}

async function save() {
  const metrics = (data.value?.metrics ?? [])
    .filter((metric) => editValues.value[metric.id] !== null)
    .map((metric) => ({ metric_id: metric.id, value: Number(editValues.value[metric.id]), note: editNotes.value[metric.id] ?? '' }))
  saving.value = true
  try {
    await saveAnalytics({ month: selectedMonth.value, metrics, summary: summary.value })
    ElMessage.success('经营数据已保存')
    await load()
  } finally {
    saving.value = false
  }
}

watch(selectedMonth, load)
onMounted(load)
</script>

<template>
  <div class="page-heading">
    <div><h1>经营分析</h1><p>核心经营指标、月度变化、趋势与复盘统一管理。</p></div>
    <div class="heading-actions">
      <ElDatePicker v-model="selectedMonth" type="month" value-format="YYYY-MM" format="YYYY年MM月" :clearable="false" />
      <ElButton :icon="Refresh" @click="load">刷新</ElButton>
      <ElButton v-if="!editing" type="primary" :icon="EditPen" @click="editing = true">录入复盘</ElButton>
      <template v-else>
        <ElButton @click="editing = false; resetEditor()">取消</ElButton>
        <ElButton type="primary" :icon="Check" :loading="saving" @click="save">保存</ElButton>
      </template>
    </div>
  </div>

  <ElAlert class="source-alert" type="success" :closable="false" show-icon title="历史数据已迁移">
    已迁入原月度复盘表中可明确识别的 2026年1月至7月数据；原表空白项保持空白，后续可按月补录。
  </ElAlert>

  <section v-loading="loading" class="metric-grid">
    <article v-for="item in headlineMetrics" :key="item.label" class="surface-card metric-card">
      <div :class="['metric-icon', item.tone]"><TrendCharts /></div>
      <div>
        <span>{{ item.label }}</span>
        <div class="metric-value">{{ displayValue(item.metric) }} <small>{{ item.metric?.unit }}</small></div>
        <p v-if="item.metric?.change_ratio !== null && item.metric?.change_ratio !== undefined">
          较上月 {{ item.metric.change_ratio > 0 ? '+' : '' }}{{ item.metric.change_ratio }}%
        </p>
        <p v-else>暂无完整环比</p>
      </div>
    </article>
  </section>

  <div class="analysis-grid">
    <section class="surface-card trend-card" v-loading="loading">
      <div class="card-heading"><div><h3>业务趋势</h3><p>已迁移月份的发货与退货走势</p></div></div>
      <VChart :option="trendOption" autoresize class="trend-chart" />
    </section>
    <section class="surface-card review-card">
      <div class="card-heading"><div><h3>月度复盘</h3><p>{{ selectedMonth }} 变化与原因</p></div><ElTag effect="plain">{{ data?.review.status === 'draft' ? '草稿' : data?.review.status }}</ElTag></div>
      <ElInput v-if="editing" v-model="summary" type="textarea" :rows="8" placeholder="录入本月整体复盘结论" />
      <div v-else class="review-copy">{{ data?.review.summary || '本月整体复盘尚未录入，可点击“录入复盘”补充。' }}</div>
      <div v-if="data?.events.length" class="event-list">
        <div v-for="event in data.events" :key="event.id"><ElTag size="small" effect="plain">{{ event.category }}</ElTag><strong>{{ event.title }}</strong><p>{{ event.description }}</p></div>
      </div>
    </section>
  </div>

  <section class="surface-card metrics-card" v-loading="loading">
    <div class="card-heading"><div><h3>月度指标明细</h3><p>当前值、上月值和原表变化原因</p></div><span>{{ data?.metrics.filter((metric) => metric.value !== null).length ?? 0 }} / {{ data?.metrics.length ?? 0 }} 项有值</span></div>
    <div v-for="group in groupedMetrics" :key="group.category" class="metric-group">
      <div class="group-title">{{ group.category }}</div>
      <ElTable :data="group.metrics" size="small">
        <ElTableColumn prop="name" label="指标" min-width="145" />
        <ElTableColumn label="本月" width="165" align="right">
          <template #default="{ row }">
            <ElInputNumber v-if="editing" v-model="editValues[row.id]" :precision="row.precision" :controls="false" />
            <strong v-else>{{ displayValue(row) }} {{ row.value === null ? '' : row.unit }}</strong>
          </template>
        </ElTableColumn>
        <ElTableColumn label="上月" width="135" align="right"><template #default="{ row }">{{ row.previous_value === null ? '—' : formatCount(row.previous_value) }} {{ row.previous_value === null ? '' : row.unit }}</template></ElTableColumn>
        <ElTableColumn label="环比" width="110" align="center">
          <template #default="{ row }"><ElTag :type="changeType(row)" effect="plain" size="small">{{ row.change_ratio === null ? '—' : `${row.change_ratio > 0 ? '+' : ''}${row.change_ratio}%` }}</ElTag></template>
        </ElTableColumn>
        <ElTableColumn label="变化原因" min-width="260">
          <template #default="{ row }"><ElInput v-if="editing" v-model="editNotes[row.id]" placeholder="可选" /><span v-else>{{ row.note || '—' }}</span></template>
        </ElTableColumn>
      </ElTable>
    </div>
  </section>
</template>

<style scoped>
.heading-actions { display:flex; align-items:center; gap:9px; }
.source-alert { margin-bottom:20px; }
.metric-grid { display:grid; margin-bottom:20px; gap:17px; grid-template-columns:repeat(4,minmax(180px,1fr)); }
.metric-card { display:flex; min-height:128px; padding:22px; align-items:center; gap:16px; }
.metric-icon { display:grid; width:43px; height:43px; flex:0 0 auto; place-items:center; border-radius:12px; }
.metric-icon svg { width:22px; }
.metric-icon.blue { color:#2f6feb; background:#eaf1ff; }.metric-icon.cyan { color:#1696ac; background:#e7f7f9; }.metric-icon.purple { color:#7356d8; background:#f0ecff; }.metric-icon.orange { color:#d7832c; background:#fff2e5; }
.metric-card span { color:#758197; font-size:12px; }.metric-value { margin-top:7px; color:#15233e; font-size:25px; font-weight:700; }.metric-value small { color:#929dad; font-size:11px; font-weight:400; }.metric-card p { margin:5px 0 0; color:#8290a4; font-size:10px; }
.analysis-grid { display:grid; margin-bottom:20px; gap:20px; grid-template-columns:minmax(500px,1.6fr) minmax(320px,.85fr); }
.trend-card,.review-card,.metrics-card { padding:24px 26px; }.card-heading { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:18px; }.card-heading h3 { margin:0 0 6px; color:#1d2a43; font-size:16px; }.card-heading p,.card-heading>span { margin:0; color:#8b96a8; font-size:11px; }
.trend-chart { width:100%; height:290px; }.review-copy { min-height:174px; padding:18px; border:1px solid #e8ecf2; border-radius:9px; color:#667389; background:#fafbfd; font-size:12px; line-height:1.9; white-space:pre-wrap; }
.event-list { margin-top:14px; }.event-list>div { padding:12px 0; border-top:1px solid #edf0f4; }.event-list strong { margin-left:8px; font-size:12px; }.event-list p { margin:6px 0 0; color:#8490a3; font-size:11px; }
.metric-group { display:grid; margin-top:15px; grid-template-columns:90px minmax(0,1fr); gap:12px; }.group-title { padding:14px; color:#2f6feb; border-radius:8px; background:#f1f6ff; font-size:13px; font-weight:700; text-align:center; align-self:stretch; }.metric-group :deep(.el-input-number) { width:135px; }
@media (max-width:1150px) { .metric-grid { grid-template-columns:repeat(2,1fr); }.analysis-grid { grid-template-columns:1fr; } }
@media (max-width:720px) { .heading-actions { flex-wrap:wrap; }.metric-grid { grid-template-columns:1fr; }.metric-group { grid-template-columns:1fr; }.group-title { text-align:left; } }
</style>
