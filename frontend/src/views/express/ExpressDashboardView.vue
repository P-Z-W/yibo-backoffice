<script setup lang="ts">
import { DataLine, Files, Operation, Setting } from '@element-plus/icons-vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import { useRouter } from 'vue-router'
import { getExpressOverview, type ExpressOverview } from '../../api/express'
import { formatCount } from '../../utils/format'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const router = useRouter()
const loading = ref(true)
const overview = ref<ExpressOverview>()

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { top: 20, right: 18, bottom: 34, left: 62 },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: overview.value?.trend.map((item) => item.month) ?? [],
    axisLine: { lineStyle: { color: '#dbe2eb' } },
    axisLabel: { color: '#8490a3' },
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#8490a3' },
    splitLine: { lineStyle: { color: '#edf1f6' } },
  },
  series: [
    {
      type: 'line',
      smooth: true,
      symbolSize: 7,
      data: overview.value?.trend.map((item) => item.amount) ?? [],
      lineStyle: { width: 3, color: '#2f6feb' },
      itemStyle: { color: '#2f6feb' },
      areaStyle: { color: 'rgba(47,111,235,.08)' },
    },
  ],
}))

onMounted(async () => {
  try {
    overview.value = await getExpressOverview()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page-heading">
    <div>
      <h1>快递对账看板</h1>
      <p>成熟对账能力和历史数据已经迁入新系统。</p>
    </div>
    <ElTag type="success" effect="light" round>完整迁移</ElTag>
  </div>

  <div v-loading="loading">
    <section class="metric-grid">
      <article class="surface-card metric-card primary">
        <span>对账月份</span>
        <strong>{{ overview?.selected_month ?? '—' }}</strong>
        <small>当前处理 {{ overview?.process_month }}</small>
      </article>
      <article class="surface-card metric-card">
        <span>运单总量</span>
        <strong>{{ formatCount(overview?.stats.total_orders) }}</strong>
        <small>匹配 {{ formatCount(overview?.stats.matched_orders) }} 单</small>
      </article>
      <article class="surface-card metric-card">
        <span>应付金额</span>
        <strong>¥ {{ formatCount(overview?.stats.total_amount) }}</strong>
        <small>{{ overview?.stats.team_stats.length ?? 0 }} 个客户团队</small>
      </article>
      <article class="surface-card metric-card warning">
        <span>未匹配运单</span>
        <strong>{{ formatCount(overview?.stats.unmatched_orders) }}</strong>
        <small>{{ overview?.stats.anomalies.length ?? 0 }} 类异常需关注</small>
      </article>
    </section>

    <section class="quick-grid">
      <button @click="router.push('/express/run')"><Operation /><span><b>运行对账</b>上传账单并执行四步流程</span></button>
      <button @click="router.push('/express/history')"><Files /><span><b>历史归档</b>查看并下载全部月份结果</span></button>
      <button @click="router.push('/express/stats')"><DataLine /><span><b>统计分析</b>团队、快递和异常分析</span></button>
      <button @click="router.push('/express/config')"><Setting /><span><b>业务配置</b>报价、客户与运行参数</span></button>
    </section>

    <div class="content-grid">
      <section class="surface-card chart-card">
        <div class="card-heading"><div><h3>月度费用趋势</h3><p>历史最终对账结果汇总</p></div></div>
        <VChart :option="chartOption" autoresize class="chart" />
      </section>

      <section class="surface-card team-card">
        <div class="card-heading"><div><h3>客户费用排行</h3><p>{{ overview?.selected_month }} TOP 8</p></div></div>
        <div v-for="(team, index) in overview?.stats.team_stats.slice(0, 8)" :key="team.team" class="team-row">
          <span class="rank">{{ index + 1 }}</span>
          <span class="team-name">{{ team.team }}</span>
          <small>{{ formatCount(team.count) }} 单</small>
          <strong>¥ {{ formatCount(team.amount) }}</strong>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.metric-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:17px; margin-bottom:18px; }
.metric-card { min-height:126px; padding:22px; display:flex; flex-direction:column; justify-content:center; }
.metric-card span { color:#7b8799; font-size:12px; }
.metric-card strong { margin:10px 0 7px; color:#172640; font-size:25px; }
.metric-card small { color:#98a2b2; font-size:10px; }
.metric-card.primary { color:#fff; border:0; background:linear-gradient(135deg,#173d78,#102b55); }
.metric-card.primary span,.metric-card.primary small { color:#9db9df; }
.metric-card.primary strong { color:#fff; }
.metric-card.warning { border-top:3px solid #e6a23c; }
.quick-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:18px; }
.quick-grid button { display:flex; align-items:center; gap:13px; padding:16px 18px; border:1px solid #e5eaf2; border-radius:12px; color:#2f6feb; background:#fff; cursor:pointer; text-align:left; transition:.2s; }
.quick-grid button:hover { transform:translateY(-2px); border-color:#bcd0f3; box-shadow:0 8px 20px rgba(32,74,133,.08); }
.quick-grid svg { width:23px; flex:0 0 auto; }
.quick-grid span { display:flex; flex-direction:column; color:#98a2b1; font-size:10px; }
.quick-grid b { margin-bottom:4px; color:#2b3850; font-size:13px; }
.content-grid { display:grid; grid-template-columns:minmax(500px,1.6fr) minmax(330px,.8fr); gap:18px; }
.chart-card,.team-card { padding:24px 26px; }
.card-heading h3 { margin:0 0 5px; color:#202e47; font-size:16px; }
.card-heading p { margin:0; color:#929cac; font-size:11px; }
.chart { height:330px; margin-top:14px; }
.team-card { min-height:405px; }
.team-row { display:grid; grid-template-columns:26px 1fr auto 105px; gap:9px; align-items:center; min-height:42px; border-bottom:1px solid #f0f2f6; font-size:11px; }
.rank { color:#9da7b6; font-weight:700; }
.team-name { overflow:hidden; color:#38455b; text-overflow:ellipsis; white-space:nowrap; }
.team-row small { color:#9aa4b3; }
.team-row strong { color:#25334c; text-align:right; }
@media(max-width:1200px){.metric-grid,.quick-grid{grid-template-columns:repeat(2,1fr)}.content-grid{grid-template-columns:1fr}}
@media(max-width:650px){.metric-grid,.quick-grid{grid-template-columns:1fr}}
</style>
