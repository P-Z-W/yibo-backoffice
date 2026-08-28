<script setup lang="ts">
import { DataLine, Files, Operation, Setting } from '@element-plus/icons-vue'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { useRouter } from 'vue-router'
import { getExpressOverview, type ExpressOverview } from '../../api/express'
import { useAuthStore } from '../../stores/auth'

use([CanvasRenderer, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent])

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const overview = ref<ExpressOverview>()
const money = (value?: number) => (value ?? 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

const currentTrend = computed(() => overview.value?.trend.find((item) => item.month === overview.value?.selected_month))
const mom = computed(() => {
  const trend = overview.value?.trend ?? []
  const index = trend.findIndex((item) => item.month === overview.value?.selected_month)
  if (index <= 0) return null
  const current = trend[index].amount
  const previous = trend[index - 1].amount
  if (!previous) return null
  const change = current - previous
  return { change, pct: (change / previous) * 100 }
})

const trendOption = computed(() => ({
  tooltip: { trigger: 'axis', valueFormatter: (value: number) => `${money(value)} 元` },
  grid: { top: 24, right: 18, bottom: 28, left: 65 },
  xAxis: { type: 'category', boundaryGap: false, data: overview.value?.trend.map((item) => item.month) ?? [], axisLabel: { color: '#8c94a6' }, axisLine: { lineStyle: { color: '#e2e6ef' } } },
  yAxis: { type: 'value', axisLabel: { color: '#8c94a6' }, splitLine: { lineStyle: { color: '#eef0f4' } } },
  series: [{ type: 'line', smooth: true, symbolSize: 6, data: overview.value?.trend.map((item) => item.amount) ?? [], lineStyle: { width: 2, color: '#2563eb' }, itemStyle: { color: '#2563eb' }, areaStyle: { color: 'rgba(37,99,235,.08)' } }],
}))

const pieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}<br/>{c} 元（{d}%）' },
  legend: { bottom: 0, textStyle: { color: '#8c94a6', fontSize: 10 } },
  color: ['#4f8ef7', '#3dd68c', '#f7954f', '#f75f5f', '#a78bfa', '#34d399', '#fb923c', '#60a5fa'],
  series: [{ type: 'pie', radius: ['43%', '68%'], center: ['50%', '43%'], label: { show: false }, data: overview.value?.stats.team_stats.slice(0, 8).map((item) => ({ name: item.team, value: item.amount })) ?? [] }],
}))

onMounted(async () => {
  try { overview.value = await getExpressOverview() } finally { loading.value = false }
})
</script>

<template>
  <div class="legacy-express" v-loading="loading">
    <h1 class="legacy-page-title"><span class="grid-icon">▦</span>数据看板<span class="sub">yibo-backoffice · v4.0</span></h1>

    <div class="dashboard-grid">
      <article class="stat-card accent"><span class="label">本月处理月份</span><strong>{{ overview?.process_month || '—' }}</strong><small>{{ overview?.recent_runs[0]?.last_time ? `上次运行：${overview.recent_runs[0].last_time}` : '暂无运行记录' }}</small></article>
      <article class="stat-card success"><span class="label">本月总费用</span><strong>{{ money(currentTrend?.amount) }}</strong><small v-if="mom" :class="mom.change > 0 ? 'mom-up' : 'mom-down'">{{ mom.change > 0 ? '↑' : '↓' }} 较上月 {{ mom.change > 0 ? '+' : '' }}{{ money(mom.change) }} 元（{{ mom.change > 0 ? '+' : '' }}{{ mom.pct.toFixed(1) }}%）</small><small v-else>暂无上月数据</small></article>
      <article class="stat-card warn"><span class="label">未匹配率</span><strong>{{ overview?.stats.total_orders ? ((overview.stats.unmatched_orders / overview.stats.total_orders) * 100).toFixed(1) : '0.0' }}%</strong><small>共 {{ (overview?.stats.unmatched_orders ?? 0).toLocaleString() }} 条未匹配</small></article>
      <article class="stat-card neutral"><span class="label">历史处理月数</span><strong>{{ overview?.months.length ?? 0 }}</strong><small>个月</small></article>
    </div>

    <div v-if="overview?.stats.express_stats.length" class="express-grid">
      <article v-for="item in overview.stats.express_stats" :key="item.name" class="stat-card neutral"><span class="label">{{ item.name }} 费用</span><strong>{{ money(item.amount) }}</strong><small>元 · {{ item.count.toLocaleString() }} 票 · 占比 {{ item.pct }}%</small></article>
      <article v-if="overview.stats.express_stats.length < 4" class="stat-card neutral"><span class="label">本月总票数</span><strong>{{ overview.stats.total_orders.toLocaleString() }}</strong><small>票</small></article>
    </div>

    <div class="charts-row">
      <section class="legacy-card chart-card"><h2 class="legacy-card-title upper">各月总费用趋势</h2><VChart v-if="overview?.trend.length" class="chart" :option="trendOption" autoresize /><div v-else class="legacy-empty">暂无历史数据，运行对账后显示</div></section>
      <section class="legacy-card chart-card"><h2 class="legacy-card-title upper">本月各团队占比</h2><VChart v-if="overview?.stats.team_stats.length" class="chart" :option="pieOption" autoresize /><div v-else class="legacy-empty">暂无团队数据</div></section>
    </div>

    <div class="bottom-row">
      <section class="legacy-card chart-card"><h2 class="legacy-card-title upper">本月团队费用 TOP 5</h2><div v-for="(team, index) in overview?.stats.team_stats.slice(0, 5)" :key="team.team" class="top5-item"><span>{{ index + 1 }}</span><b>{{ team.team }}</b><strong>{{ money(team.amount) }} 元</strong></div><div v-if="!overview?.stats.team_stats.length" class="legacy-empty">暂无数据，运行对账后显示</div></section>
      <section class="legacy-card chart-card"><h2 class="legacy-card-title upper">快速操作</h2><div class="quick-actions"><button v-if="auth.can('express.run')" @click="router.push('/express/run')"><ElIcon><Operation /></ElIcon><span>开始运行</span></button><button @click="router.push('/express/history')"><ElIcon><Files /></ElIcon><span>历史记录</span></button><button @click="router.push('/express/stats')"><ElIcon><DataLine /></ElIcon><span>统计报表</span></button><button v-if="auth.can('express.configure')" @click="router.push('/express/config')"><ElIcon><Setting /></ElIcon><span>系统配置</span></button></div></section>
    </div>
  </div>
</template>

<style scoped>
.grid-icon { color:var(--ex-accent); }
.dashboard-grid,.express-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:20px; }
.stat-card { display:flex; min-height:128px; padding:22px 20px; border:1px solid #e6e2da; border-top:3px solid var(--ex-border); border-radius:var(--ex-radius); background:#fff; box-shadow:0 2px 8px rgba(0,0,0,.04); flex-direction:column; justify-content:center; }
.stat-card.accent { border-top-color:var(--ex-accent); }.stat-card.success{border-top-color:var(--ex-success)}.stat-card.warn{border-top-color:var(--ex-warning)}
.stat-card .label { margin-bottom:8px; color:var(--ex-muted); font-size:11px; letter-spacing:.07em; text-transform:uppercase; }
.stat-card strong { color:var(--ex-text); font:700 27px Consolas,monospace; }
.stat-card.accent strong{color:var(--ex-accent)}.stat-card.success strong{color:var(--ex-success)}.stat-card.warn strong{color:var(--ex-warning)}.stat-card.neutral strong{color:#667085}
.stat-card small { margin-top:6px; color:var(--ex-muted); font-size:12px; }.stat-card small.mom-up{color:var(--ex-danger)}.stat-card small.mom-down{color:var(--ex-success)}
.charts-row { display:grid; grid-template-columns:2fr 1fr; gap:20px; margin-bottom:20px; }.bottom-row{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.chart-card { padding:22px 20px; }.chart{height:290px}
.top5-item { display:flex; align-items:center; gap:10px; min-height:40px; border-bottom:1px solid var(--ex-border); font-size:13px; }.top5-item span{width:20px;color:var(--ex-muted);font:600 11px Consolas}.top5-item b{flex:1;font-weight:400}.top5-item strong{color:var(--ex-success);font:13px Consolas}
.quick-actions{display:grid;grid-template-columns:1fr 1fr;gap:10px}.quick-actions button{display:flex;align-items:center;justify-content:center;gap:8px;min-height:75px;border:1px solid var(--ex-border);border-radius:10px;color:var(--ex-muted);background:#fff;cursor:pointer}.quick-actions button:hover{border-color:var(--ex-accent);color:var(--ex-accent);background:#f8faff}.quick-actions .el-icon{font-size:21px}.quick-actions span{font-size:12px}
@media(max-width:1100px){.dashboard-grid,.express-grid{grid-template-columns:repeat(2,1fr)}.charts-row{grid-template-columns:1fr}}@media(max-width:700px){.dashboard-grid,.express-grid,.bottom-row{grid-template-columns:1fr}}
</style>
