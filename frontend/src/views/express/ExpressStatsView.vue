<script setup lang="ts">
import { Download, Refresh, Search } from '@element-plus/icons-vue'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { useRoute } from 'vue-router'
import {
  getExpressOverview,
  getExpressPreview,
  getExpressStats,
  getUnmatchedSummary,
  type ExpressOverview,
  type ExpressPreview,
  type ExpressStats,
  type TeamSummary,
  type UnmatchedSummary,
} from '../../api/express'
import { useAuthStore } from '../../stores/auth'

use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent])

const route = useRoute()
const auth = useAuthStore()
const overview = ref<ExpressOverview>()
const months = ref<string[]>([])
const month = ref('')
const stats = ref<ExpressStats>()
const unmatched = ref<UnmatchedSummary>()
const preview = ref<ExpressPreview>()
const loading = ref(false)
const previewLoading = ref(false)
const filter = ref('all')
const keyword = ref('')
const size = ref(100)
const money = (value?: number) => (value ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const teamRowClass = ({ row }: { row: TeamSummary }) => row.team === '合计' ? 'total-row' : ''

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis' }, grid: { top: 16, right: 20, bottom: 28, left: 62 },
  xAxis: { type: 'category', boundaryGap: false, data: overview.value?.trend.map((item) => item.month) ?? [], axisLabel: { color: '#8c94a6' } },
  yAxis: { type: 'value', axisLabel: { color: '#8c94a6' }, splitLine: { lineStyle: { color: '#eef0f4' } } },
  series: [{ type: 'line', smooth: true, data: overview.value?.trend.map((item) => item.amount) ?? [], lineStyle: { color: '#2563eb', width: 2 }, itemStyle: { color: '#2563eb' }, areaStyle: { color: 'rgba(37,99,235,.07)' } }],
}))
const pieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} 元（{d}%）' }, legend: { bottom: 0, textStyle: { color: '#8c94a6', fontSize: 10 } },
  series: [{ type: 'pie', radius: ['42%', '68%'], center: ['50%', '43%'], label: { show: false }, data: stats.value?.team_stats.slice(0, 8).map((item) => ({ name: item.team, value: item.amount })) ?? [] }],
}))
const barOption = computed(() => {
  const rows = [...(stats.value?.team_stats.slice(0, 10) ?? [])].reverse()
  return { tooltip: { trigger: 'axis' }, grid: { top: 15, right: 18, bottom: 25, left: 95 }, xAxis: { type: 'value', axisLabel: { color: '#8c94a6' }, splitLine: { lineStyle: { color: '#eef0f4' } } }, yAxis: { type: 'category', data: rows.map((item) => item.team), axisLabel: { color: '#667085', width: 85, overflow: 'truncate' } }, series: [{ type: 'bar', barWidth: 12, data: rows.map((item) => item.amount), itemStyle: { color: '#16a34a', borderRadius: [0, 4, 4, 0] } }] }
})

async function loadPreview(page = 1) {
  if (!month.value) return
  previewLoading.value = true
  try { preview.value = await getExpressPreview(month.value, page, size.value, filter.value, keyword.value.trim()) } finally { previewLoading.value = false }
}

async function loadAll() {
  if (!month.value) return
  loading.value = true
  try {
    const [statsData, unmatchedData] = await Promise.all([getExpressStats(month.value), getUnmatchedSummary(month.value)])
    stats.value = statsData
    unmatched.value = unmatchedData
    await loadPreview(1)
  } finally { loading.value = false }
}

function setFilter(value: string) {
  filter.value = value
  loadPreview(1)
}

onMounted(async () => {
  overview.value = await getExpressOverview()
  months.value = overview.value.months
  const requested = typeof route.query.month === 'string' ? route.query.month : ''
  month.value = months.value.includes(requested) ? requested : overview.value.selected_month
})
watch(month, loadAll)
</script>

<template>
  <div class="legacy-express">
    <h1 class="legacy-page-title"><span class="stats-icon">▥</span>统计报表</h1>
    <div class="month-bar legacy-card"><label>处理月份</label><ElSelect v-model="month" style="width:150px"><ElOption v-for="item in months" :key="item" :label="item" :value="item" /></ElSelect><ElButton :icon="Refresh" :loading="loading" @click="loadAll">刷新数据</ElButton></div>

    <div v-loading="loading">
      <section class="legacy-card report-card">
        <h2 class="legacy-card-title upper">数据统计</h2>
        <div class="chart-grid"><div><h3>各月总费用趋势</h3><VChart class="chart" :option="trendOption" autoresize /></div><div><h3>本月各团队占比</h3><VChart class="chart" :option="pieOption" autoresize /></div><div><h3>团队费用 TOP 10</h3><VChart class="chart" :option="barOption" autoresize /></div></div>
        <h3 class="table-caption">团队计费汇总</h3>
        <ElTable :data="stats?.team_summary ?? []" border stripe :row-class-name="teamRowClass">
          <ElTableColumn prop="team" label="团队" min-width="180" />
          <ElTableColumn label="单票计费金额" min-width="150" align="right"><template #default="{ row }"><span class="money">{{ money(row.single_amount) }}</span></template></ElTableColumn>
          <ElTableColumn prop="average_count" label="全国均重票数" min-width="140" align="right" />
          <ElTableColumn label="总金额" min-width="150" align="right"><template #default="{ row }"><span class="money">{{ money(row.total_amount) }}</span></template></ElTableColumn>
        </ElTable>
      </section>

      <section class="legacy-card report-card">
        <h2 class="legacy-card-title upper">未匹配运单分析</h2>
        <div class="unmatched-grid"><article><span>总运单</span><strong>{{ unmatched?.total.toLocaleString() ?? 0 }}</strong></article><article><span>已匹配</span><strong class="green">{{ unmatched?.matched.toLocaleString() ?? 0 }}</strong></article><article><span>未匹配</span><strong class="red">{{ unmatched?.unmatched.toLocaleString() ?? 0 }}</strong></article><article><span>未匹配率</span><strong class="orange">{{ unmatched?.ratio ?? 0 }}%</strong></article></div>
        <div class="unmatched-details"><div><b>按快递分布</b><span v-for="(count, name) in unmatched?.by_express" :key="name">{{ name }}：{{ count.toLocaleString() }} 条</span><span v-if="!Object.keys(unmatched?.by_express ?? {}).length">暂无未匹配运单</span></div><div><b>示例运单号</b><span>{{ unmatched?.samples.join('、') || '暂无' }}</span></div><p>常见原因：运单不属于本店、SQL 日期范围未覆盖、运单号格式不一致。</p></div>
      </section>

      <section class="legacy-card report-card">
        <div class="report-heading"><h2 class="legacy-card-title upper">异常运单分析</h2><ElButton v-if="auth.can('express.download')" :icon="Download" tag="a" :href="`/api/v1/express/anomalies/${month}/download`">导出异常运单</ElButton></div>
        <ElCollapse v-if="stats?.anomalies.length">
          <ElCollapseItem v-for="item in stats.anomalies" :key="item.type" :name="item.type"><template #title><div class="anomaly-title"><ElTag :type="item.level === 'high' ? 'danger' : 'warning'">{{ item.level === 'high' ? '高风险' : '需关注' }}</ElTag><b>{{ item.type }}</b><span>{{ item.count.toLocaleString() }} 条 · {{ item.pct }}%</span></div></template><div class="anomaly-detail">示例运单：{{ item.samples.join('、') || '—' }}</div></ElCollapseItem>
        </ElCollapse><div v-else class="legacy-empty">本月未发现异常运单</div>
      </section>

      <section class="legacy-card report-card">
        <div class="report-heading"><h2 class="legacy-card-title upper">对账结果预览</h2><div class="preview-search"><ElInput v-model="keyword" :prefix-icon="Search" clearable placeholder="搜索运单号 / 团队" @keyup.enter="loadPreview(1)" /><ElButton type="primary" @click="loadPreview(1)">搜索</ElButton></div></div>
        <div class="filter-row"><button :class="{ active: filter === 'all' }" @click="setFilter('all')">全部 {{ preview?.total ?? 0 }}</button><button :class="{ active: filter === 'matched' }" @click="setFilter('matched')">已匹配 {{ preview?.matched ?? 0 }}</button><button :class="{ active: filter === 'unmatched' }" @click="setFilter('unmatched')">未匹配 {{ preview?.unmatched ?? 0 }}</button><button :class="{ active: filter === 'single' }" @click="setFilter('single')">单票计费</button><button :class="{ active: filter === 'average' }" @click="setFilter('average')">全国均重</button></div>
        <ElTable v-loading="previewLoading" :data="preview?.rows ?? []" height="450" border stripe><ElTableColumn prop="运单号" label="运单号" min-width="170" /><ElTableColumn prop="所属团队" label="所属团队" min-width="150" show-overflow-tooltip /><ElTableColumn prop="目的省份" label="目的省份" width="105" /><ElTableColumn prop="结算重量" label="结算重量" width="105" align="right" /><ElTableColumn prop="快递类型" label="快递类型" width="95" /><ElTableColumn prop="实际计算方式" label="实际计算方式" width="125" /><ElTableColumn label="单票应付金额" width="135" align="right"><template #default="{ row }"><span class="money">{{ money(Number(row['单票应付金额'])) }}</span></template></ElTableColumn></ElTable>
        <div class="pagination-row"><span>筛选后 {{ preview?.filtered ?? 0 }} 条</span><ElPagination v-if="preview" :current-page="preview.page" :page-size="preview.size" :total="preview.filtered" layout="prev, pager, next" @current-change="loadPreview" /></div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.stats-icon{color:var(--ex-accent)}.month-bar{display:flex;align-items:center;gap:12px;margin-bottom:20px;padding:14px 18px}.month-bar label{color:var(--ex-muted);font-size:12px}
.report-card{margin-bottom:20px;padding:22px 20px}.chart-grid{display:grid;grid-template-columns:1.4fr .8fr 1fr;gap:18px;margin-bottom:22px}.chart-grid>div{min-width:0;padding:12px;border:1px solid #eef0f4;border-radius:9px}.chart-grid h3,.table-caption{margin:0 0 10px;color:var(--ex-muted);font-size:11px;font-weight:600;letter-spacing:.05em}.chart{height:255px}.table-caption{margin-top:4px}
:deep(.total-row td){font-weight:700;background:#f8faff!important}.unmatched-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.unmatched-grid article{padding:18px;border:1px solid var(--ex-border);border-radius:9px}.unmatched-grid span{display:block;color:var(--ex-muted);font-size:11px}.unmatched-grid strong{display:block;margin-top:8px;font:700 24px Consolas}.green{color:var(--ex-success)}.red{color:var(--ex-danger)}.orange{color:var(--ex-warning)}
.unmatched-details{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}.unmatched-details>div{display:flex;gap:8px;padding:14px;border-radius:8px;background:#f8f9fb;flex-direction:column;font-size:12px}.unmatched-details b{color:var(--ex-text)}.unmatched-details span,.unmatched-details p{color:var(--ex-muted)}.unmatched-details p{grid-column:1/-1;margin:0;font-size:12px}
.report-heading{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:15px}.report-heading .legacy-card-title{margin:0}.anomaly-title{display:flex;align-items:center;gap:10px;width:100%}.anomaly-title b{font-size:13px}.anomaly-title span{margin-left:auto;margin-right:16px;color:var(--ex-muted);font-size:12px}.anomaly-detail{padding:4px 10px 10px;color:var(--ex-muted);font-size:12px}.preview-search{display:flex;gap:8px;width:360px}.filter-row{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}.filter-row button{padding:7px 13px;border:1px solid var(--ex-border);border-radius:16px;color:var(--ex-muted);background:#fff;cursor:pointer;font-size:12px}.filter-row button.active{border-color:var(--ex-accent);color:var(--ex-accent);background:#eff6ff}.pagination-row{display:flex;align-items:center;justify-content:space-between;margin-top:14px;color:var(--ex-muted);font-size:12px}
@media(max-width:1200px){.chart-grid{grid-template-columns:1fr 1fr}.chart-grid>div:first-child{grid-column:1/-1}}@media(max-width:800px){.chart-grid,.unmatched-grid,.unmatched-details{grid-template-columns:1fr}.chart-grid>div:first-child,.unmatched-details p{grid-column:auto}.report-heading{align-items:flex-start;flex-direction:column}.preview-search{width:100%}}
</style>
