<script setup lang="ts">
import {
  ArrowDown,
  Check,
  CircleCheck,
  Download,
  EditPen,
  Lock,
  OfficeBuilding,
  Refresh,
  Search,
  TrendCharts,
  Unlock,
  UploadFilled,
} from '@element-plus/icons-vue'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import { useRouter } from 'vue-router'
import {
  exportReturnItems,
  exportStaffing,
  exportShippingOrders,
  getAnalytics,
  getAnalyticsDetails,
  getAnalyticsDetailTypes,
  importAnalyticsDetails,
  previewAnalyticsImport,
  previewReturnSystemData,
  previewShippingSystemData,
  saveAnalytics,
  syncReturnSystemData,
  syncShippingSystemData,
  updateAnalyticsStatus,
  updateStaffingAnalysis,
  updateStaffingInputs,
  type AnalyticsData,
  type AnalyticsDetails,
  type AnalyticsDetailType,
  type AnalyticsImportPreview,
  type AnalyticsMetric,
  type ReturnSystemPreview,
  type ShippingSystemPreview,
} from '../api/analytics'
import { formatCount } from '../utils/format'
import { useAuthStore } from '../stores/auth'

use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent])

const auth = useAuthStore()
const router = useRouter()
const selectedMonth = ref('2026-07')
const data = ref<AnalyticsData>()
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const editValues = ref<Record<number, number | null>>({})
const editNotes = ref<Record<number, string>>({})
const summary = ref('')
const highlights = ref('')
const issues = ref('')
const risks = ref('')
const nextPlan = ref('')
const activeTab = ref('summary')
const detailTypes = ref<AnalyticsDetailType[]>([])
const details = ref<AnalyticsDetails>()
const detailLoading = ref(false)
const detailPage = ref(1)
const detailPageSize = ref(50)
const previewVisible = ref(false)
const previewLoading = ref(false)
const importing = ref(false)
const previewFile = ref<File>()
const importPreview = ref<AnalyticsImportPreview>()
const importMode = ref<'replace' | 'append'>('replace')
const statusLoading = ref(false)
const systemPreviewVisible = ref(false)
const systemPreviewLoading = ref(false)
const systemSyncing = ref(false)
const shippingSystemPreview = ref<ShippingSystemPreview>()
const returnSystemPreview = ref<ReturnSystemPreview>()
const shippingChartVisible = ref(false)
const shippingChartLoading = ref(false)
const shippingChartRows = ref<AnalyticsDetails['rows']>([])
const chartDataset = ref<'shipping_orders' | 'return_items'>('shipping_orders')
const shippingTeamSearch = ref('')
const returnTeamSearch = ref('')
const staffingTeamSearch = ref('')
const staffingAnalysisEditingId = ref<number>()
const staffingAnalysisSavingId = ref<number>()
const staffingAnalysisDraft = ref<string[]>(['', '', ''])
const staffingInputsEditingId = ref<number>()
const staffingInputsSavingId = ref<number>()
const shippingSortOrder = ref<'' | 'asc' | 'desc'>('')
const returnSortOrder = ref<'' | 'asc' | 'desc'>('')
const detailFileInput = ref<HTMLInputElement>()
const shippingSelectedRows = ref<AnalyticsDetails['rows']>([])
const exportVisible = ref(false)
const exportLoading = ref(false)
const returnExportLoading = ref(false)
const staffingExportLoading = ref(false)
const exportScope = ref<'filtered' | 'selected'>('filtered')
const exportColumns = ref<Array<'团队名称' | '发货单量' | '数据发货占比'>>([
  '团队名称',
  '发货单量',
  '数据发货占比',
])
let shippingSearchTimer: number | undefined
let returnSearchTimer: number | undefined
let staffingSearchTimer: number | undefined
let analyticsLoadId = 0
let detailLoadId = 0

type MatrixChangeMode = 'current' | 'difference'
interface MatrixRowDefinition {
  code: string
  label: string
  changeMode: MatrixChangeMode
  detailCode?: string
}

interface ShippingChartTeam {
  name: string
  value: number
  share: number
}

const staffingEditableColumns = [
  '正式工人数',
  '最优配置',
  '人均月产出',
  '最优人均产出',
] as const
type StaffingEditableColumn = (typeof staffingEditableColumns)[number]
const staffingInputsDraft = ref<Record<StaffingEditableColumn, number | null>>({
  正式工人数: null,
  最优配置: null,
  人均月产出: null,
  最优人均产出: null,
})

const staffingAnalysisHeadings = [
  '配置分析',
  '人均月产出分析',
  '人均月产出环比分析',
] as const

const reviewMatrixDefinitions: Array<{ category: string; rows: MatrixRowDefinition[] }> = [
  {
    category: '发货',
    rows: [
      { code: 'shipping_orders', label: '发货单量', changeMode: 'current', detailCode: 'shipping_orders' },
      { code: 'shipping_customer_change', label: '发货客户变化', changeMode: 'current' },
      { code: 'shipping_value_added', label: '发货增值', changeMode: 'difference' },
    ],
  },
  {
    category: '退货',
    rows: [
      { code: 'return_items', label: '退货件数', changeMode: 'current', detailCode: 'return_items' },
      { code: 'return_customer_change', label: '退货客户变化', changeMode: 'current' },
      { code: 'return_value_added', label: '退件增值', changeMode: 'difference' },
    ],
  },
  {
    category: '客户',
    rows: [
      { code: 'new_customers', label: '新进客户', changeMode: 'current', detailCode: 'customer_changes' },
      { code: 'lost_customers', label: '流失客户', changeMode: 'current', detailCode: 'customer_changes' },
      { code: 'prospective_customers', label: '意向客户', changeMode: 'current', detailCode: 'customer_changes' },
    ],
  },
  {
    category: '供应商',
    rows: [
      { code: 'supplier_change', label: '供应商变化', changeMode: 'difference', detailCode: 'supplier_changes' },
      { code: 'express_adjustment', label: '快递调整', changeMode: 'difference' },
    ],
  },
  {
    category: '人员场地',
    rows: [
      { code: 'staff_adjustment', label: '人员调整', changeMode: 'difference', detailCode: 'staffing' },
      { code: 'site_adjustment', label: '场地调整', changeMode: 'difference' },
    ],
  },
  {
    category: '其他',
    rows: [
      { code: 'planning_adjustment', label: '规划调整', changeMode: 'difference' },
      { code: 'system_optimization', label: '系统优化', changeMode: 'difference' },
    ],
  },
]

const currentDetailType = computed(() => detailTypes.value.find((item) => item.code === activeTab.value))
const isSystemDataset = computed(() => ['shipping_orders', 'return_items'].includes(activeTab.value))
const activeSystemPreview = computed(() => (
  activeTab.value === 'return_items' ? returnSystemPreview.value : shippingSystemPreview.value
))
const systemMetricLabel = computed(() => (
  activeTab.value === 'return_items' ? '退货件数合计' : '发货单量'
))
const systemMetricUnit = computed(() => (activeTab.value === 'return_items' ? '件' : '单'))
const systemSummaryTotal = computed(() => (
  activeTab.value === 'return_items'
    ? details.value?.summary.return_items ?? 0
    : details.value?.summary.shipping_orders ?? 0
))
const visibleDetailColumns = computed(() => (details.value?.columns ?? []).filter(
  (column) => activeTab.value !== 'shipping_orders' || column !== '备注',
))
const managedDetailRoutes: Record<string, { label: string; route: string }> = {
  customer_changes: { label: '客户管理', route: '/customers' },
  supplier_changes: { label: '供应商管理', route: '/suppliers' },
  value_added: { label: '增值服务', route: '/value-added' },
  service_issues: { label: '客户服务管理', route: '/customer-service' },
  short_video: { label: '短视频管理', route: '/short-video' },
}
const detailManagement = computed(() => managedDetailRoutes[activeTab.value])
const templateUrl = computed(() => {
  const base = `/api/v1/analytics/details/${activeTab.value}/template`
  return activeTab.value === 'shipping_orders'
    ? `${base}?month=${encodeURIComponent(selectedMonth.value)}`
    : base
})
const isArchived = computed(() => data.value?.review.status === 'archived')
const canManage = computed(() => auth.can('analytics.manage') && !isArchived.value)
const statusInfo = computed(() => {
  const status = data.value?.review.status ?? 'draft'
  if (status === 'archived') return { label: '已归档', type: 'info' as const, hint: '本月数据已锁定' }
  if (status === 'completed') return { label: '已完成', type: 'success' as const, hint: '本月数据已整理完成' }
  return { label: '编辑中', type: 'warning' as const, hint: '数据和复盘仍可继续补充' }
})
const reviewSections = computed(() => [
  { label: '经营亮点', value: data.value?.review.highlights },
  { label: '主要问题及原因', value: data.value?.review.issues },
  { label: '风险与协同事项', value: data.value?.review.risks },
  { label: '下月重点工作', value: data.value?.review.next_plan },
].filter((item) => item.value))

function metricByCode(code: string) {
  return data.value?.metrics.find((metric) => metric.code === code)
}

const reviewMatrix = computed(() => reviewMatrixDefinitions.map((group) => ({
  ...group,
  rows: group.rows.map((row) => ({ ...row, metric: metricByCode(row.code) })),
})))
const reviewMonths = computed(() => [selectedMonth.value])
const reviewMatrixWidth = computed(() => 910 + reviewMonths.value.length * 112)
const selectedMonthLabel = computed(() => {
  const [year, month] = selectedMonth.value.split('-').map(Number)
  return `${year}年${month}月`
})
const staffingSummaryCards = computed(() => {
  const values = details.value?.summary ?? {}
  return [
    { label: '正式工人数', value: values.staff_regular_total ?? 0, unit: '人', tone: 'primary' },
    { label: '最优配置', value: values.staff_optimal_total ?? 0, unit: '人', tone: 'violet' },
    { label: '总配置偏差', value: values.staff_configuration_gap ?? 0, unit: '人', tone: 'amber' },
    { label: '超配小组', value: values.staff_overstaffed_groups ?? 0, unit: '组', tone: 'warning' },
    { label: '缺编小组', value: values.staff_understaffed_groups ?? 0, unit: '组', tone: 'danger' },
  ]
})

function matrixMonthLabel(month: string) {
  const [year, value] = month.split('-').map(Number)
  return `${year}年${value}月`
}

function matrixValue(code: string, month: string) {
  if (month === selectedMonth.value) {
    const current = metricByCode(code)?.value
    if (current !== null && current !== undefined) return current
  }
  return data.value?.trend[code]?.find((item) => item.month === month)?.value ?? null
}

function matrixChange(row: MatrixRowDefinition) {
  const current = matrixValue(row.code, selectedMonth.value)
  if (current === null) return null
  if (row.changeMode === 'current') return current
  const previous = matrixValue(row.code, data.value?.previous_month ?? '')
  return previous === null ? null : current - previous
}

function matrixRatio(row: MatrixRowDefinition) {
  const previous = matrixValue(row.code, data.value?.previous_month ?? '')
  const change = matrixChange(row)
  if (previous === null || previous === 0 || change === null) return null
  return change / previous * 100
}

function formatMatrixNumber(value: number | null, metric?: AnalyticsMetric) {
  if (value === null) return '—'
  return metric?.precision ? value.toFixed(metric.precision) : formatCount(value)
}

function formatMatrixRatio(row: MatrixRowDefinition) {
  const ratio = matrixRatio(row)
  return ratio === null ? '—' : `${ratio.toFixed(2)}%`
}

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

const shippingChartTeams = computed<ShippingChartTeam[]>(() => {
  const valueColumn = chartDataset.value === 'return_items' ? '退货件数合计' : '发货单量'
  const rows = shippingChartRows.value
    .map((row) => ({
      name: String(row.values.团队名称 || '未命名团队'),
      value: Number(row.values[valueColumn] || 0),
    }))
    .filter((row) => Number.isFinite(row.value) && row.value >= 0)
    .sort((left, right) => right.value - left.value)
  const total = rows.reduce((sum, row) => sum + row.value, 0)
  return rows.map((row) => ({
    ...row,
    share: total ? row.value / total * 100 : 0,
  }))
})

const chartIsReturn = computed(() => chartDataset.value === 'return_items')
const chartMetricLabel = computed(() => chartIsReturn.value ? '退货件数' : '发货量')
const chartMetricUnit = computed(() => chartIsReturn.value ? '件' : '单')
const chartSearchText = computed(() => chartIsReturn.value ? returnTeamSearch.value : shippingTeamSearch.value)

const shippingChartStats = computed(() => {
  const teams = shippingChartTeams.value
  const total = teams.reduce((sum, row) => sum + row.value, 0)
  const sortedValues = teams.map((row) => row.value).sort((left, right) => left - right)
  const middle = Math.floor(sortedValues.length / 2)
  const median = sortedValues.length
    ? sortedValues.length % 2
      ? sortedValues[middle]
      : (sortedValues[middle - 1] + sortedValues[middle]) / 2
    : 0
  const topFive = teams.slice(0, 5).reduce((sum, row) => sum + row.value, 0)
  return {
    total,
    teamCount: teams.length,
    average: teams.length ? total / teams.length : 0,
    median,
    topTeam: teams[0],
    topFiveShare: total ? topFive / total * 100 : 0,
  }
})

const shippingRankingOption = computed(() => {
  const rows = shippingChartTeams.value.slice(0, 12).reverse()
  const colors = chartIsReturn.value ? ['#55c3b8', '#1e9d91'] : ['#77a9ff', '#3978e6']
  return {
    animationDuration: 650,
    grid: { top: 18, right: 72, bottom: 28, left: 118 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (value: unknown) => `${formatCount(Number(value))} ${chartMetricUnit.value}`,
    },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#edf2f8' } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => row.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#55647a', width: 100, overflow: 'truncate' },
    },
    series: [{
      name: chartMetricLabel.value,
      type: 'bar',
      barWidth: 17,
      data: rows.map((row) => row.value),
      label: { show: true, position: 'right', color: '#52617a', formatter: '{c}' },
      itemStyle: {
        borderRadius: [0, 8, 8, 0],
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 1,
          y2: 0,
          colorStops: [
            { offset: 0, color: colors[0] },
            { offset: 1, color: colors[1] },
          ],
        },
      },
    }],
  }
})

const shippingShareOption = computed(() => {
  const topTeams = shippingChartTeams.value.slice(0, 7)
  const otherValue = shippingChartTeams.value.slice(7).reduce((sum, row) => sum + row.value, 0)
  const chartRows = [
    ...topTeams.map((row) => ({ name: row.name, value: row.value })),
    ...(otherValue ? [{ name: '其他团队', value: otherValue }] : []),
  ]
  return {
    animationDuration: 700,
    color: ['#3f7ee8', '#57a4f8', '#61c0bf', '#7d6ce5', '#f0a64a', '#ef7d73', '#80b36f', '#b4bdca'],
    tooltip: {
      trigger: 'item',
      valueFormatter: (value: unknown) => `${formatCount(Number(value))} ${chartMetricUnit.value}`,
    },
    legend: { type: 'scroll', bottom: 0, left: 'center', icon: 'circle', itemWidth: 8, itemHeight: 8 },
    series: [{
      name: '团队占比',
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['50%', '43%'],
      avoidLabelOverlap: true,
      itemStyle: { borderColor: '#fff', borderWidth: 3, borderRadius: 5 },
      label: { color: '#52617a', formatter: '{b}\n{d}%' },
      emphasis: { scaleSize: 8, label: { fontWeight: 700 } },
      data: chartRows,
    }],
  }
})

const shippingVolumeTrendOption = computed(() => {
  const rows = (data.value?.trend[chartDataset.value] ?? []).slice(-12)
  const color = chartIsReturn.value ? '#1e9d91' : '#3978e6'
  return {
    animationDuration: 650,
    grid: { top: 24, right: 28, bottom: 34, left: 62 },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: unknown) => `${formatCount(Number(value))} ${chartMetricUnit.value}`,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((row) => row.month),
      axisLine: { lineStyle: { color: '#dce4ef' } },
      axisLabel: { color: '#718096' },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#718096' },
      splitLine: { lineStyle: { color: '#edf2f8' } },
    },
    series: [{
      name: `月度${chartMetricLabel.value}`,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 8,
      data: rows.map((row) => row.value),
      lineStyle: { width: 3, color },
      itemStyle: { color, borderColor: '#fff', borderWidth: 2 },
      areaStyle: { color: chartIsReturn.value ? 'rgba(30,157,145,.12)' : 'rgba(63,126,232,.12)' },
    }],
  }
})

const returnComponentOption = computed(() => {
  const rows = shippingChartRows.value
    .map((row) => ({
      name: String(row.values.团队名称 || '未命名团队'),
      handled: Number(row.values.处理退货件数 || 0),
      intercepted: Number(row.values.拦截件扣费件数 || 0),
      unusual: Number(row.values.异常件扣费件数 || 0),
      total: Number(row.values.退货件数合计 || 0),
    }))
    .sort((left, right) => right.total - left.total)
    .slice(0, 10)
    .reverse()
  return {
    animationDuration: 700,
    color: ['#2d8fe8', '#f1a54a', '#e96b78'],
    grid: { top: 42, right: 52, bottom: 28, left: 118 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 12, itemHeight: 7 },
    xAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: '#edf2f8' } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => row.name),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#55647a', width: 100, overflow: 'truncate' },
    },
    series: [
      { name: '处理退货件数', type: 'bar', stack: 'return', barWidth: 17, data: rows.map((row) => row.handled) },
      { name: '拦截件扣费件数', type: 'bar', stack: 'return', barWidth: 17, data: rows.map((row) => row.intercepted) },
      {
        name: '异常件扣费件数',
        type: 'bar',
        stack: 'return',
        barWidth: 17,
        data: rows.map((row) => row.unusual),
        itemStyle: { borderRadius: [0, 8, 8, 0] },
      },
    ],
  }
})

function resetEditor() {
  editValues.value = Object.fromEntries((data.value?.metrics ?? []).map((metric) => [metric.id, metric.value]))
  editNotes.value = Object.fromEntries((data.value?.metrics ?? []).map((metric) => [metric.id, metric.note]))
  summary.value = data.value?.review.summary ?? ''
  highlights.value = data.value?.review.highlights ?? ''
  issues.value = data.value?.review.issues ?? ''
  risks.value = data.value?.review.risks ?? ''
  nextPlan.value = data.value?.review.next_plan ?? ''
}

function beginEditing() {
  if (isArchived.value) {
    ElMessage.warning('该月份已归档，请先重新开启')
    return
  }
  editing.value = true
}

async function load() {
  const requestId = ++analyticsLoadId
  const month = selectedMonth.value
  loading.value = true
  try {
    const result = await getAnalytics(month)
    if (requestId !== analyticsLoadId || month !== selectedMonth.value) return
    data.value = result
    resetEditor()
    editing.value = false
  } finally {
    if (requestId === analyticsLoadId) loading.value = false
  }
}

async function loadDetails() {
  if (activeTab.value === 'summary') return
  const requestId = ++detailLoadId
  const dataset = activeTab.value
  const month = selectedMonth.value
  detailLoading.value = true
  try {
    const result = await getAnalyticsDetails(
      dataset,
      month,
      detailPage.value,
      detailPageSize.value,
      dataset === 'shipping_orders'
        ? { search: shippingTeamSearch.value, sortOrder: shippingSortOrder.value }
        : dataset === 'return_items'
          ? { search: returnTeamSearch.value, sortOrder: returnSortOrder.value }
        : dataset === 'staffing'
          ? { search: staffingTeamSearch.value }
          : undefined,
    )
    if (
      requestId !== detailLoadId
      || dataset !== activeTab.value
      || month !== selectedMonth.value
    ) return
    details.value = result
  } finally {
    if (requestId === detailLoadId) detailLoading.value = false
  }
}

async function openSystemCharts() {
  if (activeTab.value !== 'shipping_orders' && activeTab.value !== 'return_items') return
  chartDataset.value = activeTab.value
  const dataset = chartDataset.value
  const search = dataset === 'return_items' ? returnTeamSearch.value : shippingTeamSearch.value
  shippingChartVisible.value = true
  shippingChartLoading.value = true
  shippingChartRows.value = []
  try {
    const firstPage = await getAnalyticsDetails(dataset, selectedMonth.value, 1, 200, {
      search,
      sortOrder: 'desc',
    })
    const pageCount = Math.ceil(firstPage.total / 200)
    const remainingPages = pageCount > 1
      ? await Promise.all(
        Array.from({ length: pageCount - 1 }, (_, index) => getAnalyticsDetails(
          dataset,
          selectedMonth.value,
          index + 2,
          200,
          { search, sortOrder: 'desc' },
        )),
      )
      : []
    shippingChartRows.value = [firstPage, ...remainingPages].flatMap((page) => page.rows)
  } catch (error) {
    shippingChartVisible.value = false
    ElMessage.error(errorText(error))
  } finally {
    shippingChartLoading.value = false
  }
}

async function refreshActive() {
  if (activeTab.value === 'summary') await load()
  else await Promise.all([load(), loadDetails()])
}

function errorText(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || '操作失败，请稍后重试'
}

function displayDetailValue(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

const staffingPercentColumns = new Set(['偏差比例', '效率差额占比', '人均月产出环比'])
const staffingCountColumns = new Set(['正式工人数', '最优配置', '配置偏差'])
const staffingDecimalColumns = new Set(['人均月产出', '最优人均产出', '效率差额', '人均月产出净变化'])
const returnCountColumns = new Set([
  '处理退货件数',
  '拦截件扣费件数',
  '异常件扣费件数',
  '退货件数合计',
])

function displayColumnValue(column: string, value: string | number | boolean | null | undefined) {
  if (activeTab.value !== 'staffing') return displayDetailValue(value)
  if (value === null || value === undefined || value === '') return '—'
  const numeric = Number(value)
  if (staffingPercentColumns.has(column) && Number.isFinite(numeric)) {
    return `${(numeric * 100).toFixed(2)}%`
  }
  if (staffingCountColumns.has(column) && Number.isFinite(numeric)) {
    return numeric.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  }
  if (staffingDecimalColumns.has(column) && Number.isFinite(numeric)) {
    return numeric.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }
  return displayDetailValue(value)
}

function staffingGapTagType(value: unknown) {
  const gap = Number(value)
  if (!Number.isFinite(gap) || gap === 0) return 'success'
  return gap > 0 ? 'warning' : 'danger'
}

function staffingGapLabel(value: unknown) {
  const gap = Number(value)
  if (!Number.isFinite(gap)) return '—'
  if (gap === 0) return '配置合理'
  return gap > 0 ? `超配 ${gap}` : `缺编 ${Math.abs(gap)}`
}

function staffingInputNumber(value: unknown) {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function isStaffingEditableColumn(column: string): column is StaffingEditableColumn {
  return staffingEditableColumns.includes(column as StaffingEditableColumn)
}

function staffingInputDraftValue(column: string) {
  return isStaffingEditableColumn(column) ? staffingInputsDraft.value[column] : null
}

function updateStaffingInputDraft(column: string, value: number | undefined) {
  if (isStaffingEditableColumn(column)) staffingInputsDraft.value[column] = value ?? null
}

function beginStaffingInputsEdit(row: AnalyticsDetails['rows'][number]) {
  if (!canManage.value) {
    ElMessage.warning(isArchived.value ? '该月份已归档，请先重新开启' : '当前账号没有编辑权限')
    return
  }
  cancelStaffingAnalysisEdit()
  staffingInputsEditingId.value = row.id
  staffingInputsDraft.value = Object.fromEntries(
    staffingEditableColumns.map((column) => [column, staffingInputNumber(row.values[column])]),
  ) as Record<StaffingEditableColumn, number | null>
}

function cancelStaffingInputsEdit() {
  staffingInputsEditingId.value = undefined
  staffingInputsDraft.value = {
    正式工人数: null,
    最优配置: null,
    人均月产出: null,
    最优人均产出: null,
  }
}

async function saveStaffingInputs(row: AnalyticsDetails['rows'][number]) {
  const regularStaff = staffingInputsDraft.value.正式工人数
  if (regularStaff === null) {
    ElMessage.warning('正式工人数不能为空')
    return
  }
  staffingInputsSavingId.value = row.id
  try {
    const result = await updateStaffingInputs(row.id, {
      month: selectedMonth.value,
      team_name: String(row.values.小组 ?? ''),
      regular_staff: regularStaff,
      optimal_staff: staffingInputsDraft.value.最优配置,
      monthly_output: staffingInputsDraft.value.人均月产出,
      optimal_monthly_output: staffingInputsDraft.value.最优人均产出,
    })
    row.id = result.row_id
    row.values = result.values
    cancelStaffingInputsEdit()
    ElMessage.success('人员调整基础值已保存，派生指标已重新计算')
    await Promise.all([load(), loadDetails()])
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    staffingInputsSavingId.value = undefined
  }
}

function parseStaffingAnalysis(value: unknown) {
  const text = String(value ?? '').replace(/\r\n/g, '\n').trim()
  if (!text) return ['', '', '']

  const markerPattern = /([123])\s*[、.．]\s*(配置分析|人均月产出分析|人均月产出环比分析)\s*[。.:：]?\s*/g
  const markers = [...text.matchAll(markerPattern)]
  if (!markers.length) return [text, '', '']

  const sections = ['', '', '']
  markers.forEach((marker, index) => {
    const headingIndex = staffingAnalysisHeadings.indexOf(
      marker[2] as (typeof staffingAnalysisHeadings)[number],
    )
    if (headingIndex < 0) return
    const start = (marker.index ?? 0) + marker[0].length
    const end = markers[index + 1]?.index ?? text.length
    sections[headingIndex] = text
      .slice(start, end)
      .trim()
      .replace(/^[；;]\s*/, '')
      .replace(/\s*[；;]$/, '')
  })
  return sections
}

function staffingAnalysisSections(value: unknown) {
  const sections = parseStaffingAnalysis(value)
  return staffingAnalysisHeadings.map((heading, index) => ({
    heading,
    text: sections[index],
  }))
}

function beginStaffingAnalysisEdit(row: AnalyticsDetails['rows'][number]) {
  if (!canManage.value) {
    ElMessage.warning(isArchived.value ? '该月份已归档，请先重新开启' : '当前账号没有编辑权限')
    return
  }
  cancelStaffingInputsEdit()
  staffingAnalysisEditingId.value = row.id
  staffingAnalysisDraft.value = parseStaffingAnalysis(row.values.综合分析)
}

function cancelStaffingAnalysisEdit() {
  staffingAnalysisEditingId.value = undefined
  staffingAnalysisDraft.value = ['', '', '']
}

async function saveStaffingAnalysis(row: AnalyticsDetails['rows'][number]) {
  const analysis = staffingAnalysisHeadings
    .map((heading, index) => `${index + 1}、${heading}。${staffingAnalysisDraft.value[index]?.trim() ?? ''}`)
    .join('\n')
  staffingAnalysisSavingId.value = row.id
  try {
    const result = await updateStaffingAnalysis(row.id, selectedMonth.value, analysis)
    row.values = { ...row.values, 综合分析: result.analysis }
    cancelStaffingAnalysisEdit()
    ElMessage.success('综合分析已保存')
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    staffingAnalysisSavingId.value = undefined
  }
}

function detailRowIndex(index: number) {
  return (detailPage.value - 1) * detailPageSize.value + index + 1
}

function detailColumnWidth(column: string) {
  if (activeTab.value === 'shipping_orders') {
    if (column === '团队名称') return 220
    if (column === '发货单量') return 140
    if (column === '数据发货占比') return 150
  }
  if (activeTab.value === 'return_items') {
    if (column === '团队名称') return 220
    if (column === '数据退货占比') return 150
    return 165
  }
  if (activeTab.value === 'staffing') {
    if (column === '小组') return 150
    if (column === '综合分析') return 600
    if (staffingCountColumns.has(column)) return 118
    if (staffingPercentColumns.has(column)) return 135
    return 150
  }
  if (column === '团队名称') return 260
  if (column === '备注') return 360
  return 180
}

function detailColumnAlign(column: string) {
  if (activeTab.value === 'return_items') {
    return column === '团队名称' ? 'left' : 'right'
  }
  if (activeTab.value === 'staffing') {
    return column === '小组' || column === '综合分析' ? 'left' : 'right'
  }
  return ['发货单量', '数据发货占比'].includes(column) ? 'right' : 'left'
}

function displayShippingShare(value: unknown) {
  const share = Number(value)
  return Number.isFinite(share) ? `${share.toFixed(2)}%` : '—'
}

function displayConsumptionAmount(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  const amount = Number(value)
  return Number.isFinite(amount)
    ? `¥${amount.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : '—'
}

function shippingSnapshotTagType(state?: string) {
  if (state === 'current') return 'success'
  if (state === 'review') return 'primary'
  if (state === 'future') return 'warning'
  return 'info'
}

function metricName(code: string) {
  return data.value?.metrics.find((metric) => metric.code === code)?.name || code
}

function formatImportedAt(value: string) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatActivity(value?: string | null) {
  return value ? formatImportedAt(value) : '暂无更新记录'
}

function openDataset(code: string) {
  activeTab.value = code
}

async function onDetailFile(file: { raw?: File }) {
  if (!file.raw || activeTab.value === 'summary') return
  previewFile.value = file.raw
  previewLoading.value = true
  try {
    importPreview.value = await previewAnalyticsImport(
      activeTab.value,
      file.raw,
      selectedMonth.value,
    )
    importMode.value = 'replace'
    previewVisible.value = true
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    previewLoading.value = false
  }
}

function handleExcelCommand(command: 'download' | 'upload' | 'export') {
  if (command === 'download') {
    const link = document.createElement('a')
    link.href = templateUrl.value
    link.click()
    return
  }
  if (command === 'export') {
    void exportStaffingData()
    return
  }
  detailFileInput.value?.click()
}

async function exportStaffingData() {
  staffingExportLoading.value = true
  try {
    const blob = await exportStaffing(selectedMonth.value)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${selectedMonth.value} 人员调整导出.xlsx`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('人员调整数据已导出')
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    staffingExportLoading.value = false
  }
}

function onNativeDetailFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) void onDetailFile({ raw: file })
  input.value = ''
}

function onShippingSelectionChange(rows: AnalyticsDetails['rows']) {
  shippingSelectedRows.value = rows
}

function openShippingExport() {
  exportScope.value = shippingSelectedRows.value.length ? 'selected' : 'filtered'
  exportVisible.value = true
}

async function commitShippingExport() {
  if (!exportColumns.value.length) {
    ElMessage.warning('请至少选择一个导出字段')
    return
  }
  if (exportScope.value === 'selected' && !shippingSelectedRows.value.length) {
    ElMessage.warning('请先勾选需要导出的团队')
    return
  }
  exportLoading.value = true
  try {
    const blob = await exportShippingOrders({
      month: selectedMonth.value,
      scope: exportScope.value,
      row_ids: shippingSelectedRows.value.map((row) => row.id),
      columns: exportColumns.value,
      search: shippingTeamSearch.value,
      sort_order: shippingSortOrder.value,
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${selectedMonth.value} 发货单量导出.xlsx`
    link.click()
    URL.revokeObjectURL(url)
    exportVisible.value = false
    ElMessage.success('发货数据已导出')
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    exportLoading.value = false
  }
}

async function exportReturnData() {
  returnExportLoading.value = true
  try {
    const blob = await exportReturnItems(selectedMonth.value, {
      search: returnTeamSearch.value,
      sortOrder: returnSortOrder.value,
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${selectedMonth.value} 退货件数导出.xlsx`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('退货数据已导出')
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    returnExportLoading.value = false
  }
}

async function openSystemPreview() {
  systemPreviewLoading.value = true
  try {
    if (activeTab.value === 'return_items') {
      returnSystemPreview.value = await previewReturnSystemData(selectedMonth.value)
    } else {
      shippingSystemPreview.value = await previewShippingSystemData(selectedMonth.value)
    }
    systemPreviewVisible.value = true
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    systemPreviewLoading.value = false
  }
}

async function commitSystemData() {
  systemSyncing.value = true
  try {
    const result = activeTab.value === 'return_items'
      ? await syncReturnSystemData(
        selectedMonth.value,
        returnSystemPreview.value?.requires_confirmation ?? false,
      )
      : await syncShippingSystemData(
        selectedMonth.value,
        shippingSystemPreview.value?.requires_confirmation ?? false,
      )
    systemPreviewVisible.value = false
    shippingSelectedRows.value = []
    ElMessage.success(
      `${result.message}，合计 ${formatCount(result.total)} ${systemMetricUnit.value}`,
    )
    await Promise.all([load(), loadDetails()])
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    systemSyncing.value = false
  }
}

async function commitImport() {
  if (!previewFile.value || activeTab.value === 'summary') return
  importing.value = true
  try {
    const result = await importAnalyticsDetails(
      activeTab.value,
      selectedMonth.value,
      importMode.value,
      previewFile.value,
    )
    previewVisible.value = false
    shippingSelectedRows.value = []
    const summaryMessage = result.updated_metrics.length
      ? `，并更新 ${result.updated_metrics.map((item) => item.name).join('、')}`
      : ''
    ElMessage.success(`${result.message}${summaryMessage}`)
    if (result.warnings.length) ElMessage.warning(result.warnings.join('；'))
    await Promise.all([load(), loadDetails()])
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    importing.value = false
  }
}

async function changeDetailPage(page: number) {
  detailPage.value = page
  await loadDetails()
}

async function changeDetailPageSize(pageSize: number) {
  detailPageSize.value = pageSize
  detailPage.value = 1
  await loadDetails()
}

function scheduleShippingSearch() {
  if (shippingSearchTimer !== undefined) window.clearTimeout(shippingSearchTimer)
  shippingSearchTimer = window.setTimeout(async () => {
    detailPage.value = 1
    await loadDetails()
  }, 250)
}

function scheduleReturnSearch() {
  if (returnSearchTimer !== undefined) window.clearTimeout(returnSearchTimer)
  returnSearchTimer = window.setTimeout(async () => {
    detailPage.value = 1
    await loadDetails()
  }, 250)
}

function scheduleStaffingSearch() {
  if (staffingSearchTimer !== undefined) window.clearTimeout(staffingSearchTimer)
  staffingSearchTimer = window.setTimeout(async () => {
    detailPage.value = 1
    await loadDetails()
  }, 250)
}

async function changeDetailSort({
  prop,
  order,
}: {
  prop: string
  order: 'ascending' | 'descending' | null
}) {
  const sortOrder = order === 'ascending' ? 'asc' : order === 'descending' ? 'desc' : ''
  if (activeTab.value === 'shipping_orders' && prop === '发货单量') {
    shippingSortOrder.value = sortOrder
  } else if (activeTab.value === 'return_items' && prop === '退货件数合计') {
    returnSortOrder.value = sortOrder
  } else {
    return
  }
  detailPage.value = 1
  await loadDetails()
}

async function save() {
  const metrics = (data.value?.metrics ?? [])
    .filter((metric) => editValues.value[metric.id] !== null)
    .map((metric) => ({ metric_id: metric.id, value: Number(editValues.value[metric.id]), note: editNotes.value[metric.id] ?? '' }))
  saving.value = true
  try {
    await saveAnalytics({
      month: selectedMonth.value,
      metrics,
      summary: summary.value,
      highlights: highlights.value,
      issues: issues.value,
      risks: risks.value,
      next_plan: nextPlan.value,
    })
    ElMessage.success('经营数据已保存')
    await load()
  } finally {
    saving.value = false
  }
}

async function changeStatus(status: 'draft' | 'completed' | 'archived') {
  const copy = status === 'archived'
    ? ['归档后本月数据和分表将锁定，确认归档吗？', '归档本月']
    : status === 'draft'
      ? ['重新开启后可以继续修改本月数据，确认吗？', '重新开启']
      : ['标记完成后仍可继续编辑或归档，确认吗？', '标记完成']
  try {
    await ElMessageBox.confirm(copy[0], copy[1], {
      confirmButtonText: copy[1],
      cancelButtonText: '取消',
      type: status === 'archived' ? 'warning' : 'info',
    })
    statusLoading.value = true
    const result = await updateAnalyticsStatus(selectedMonth.value, status)
    ElMessage.success(result.message)
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error))
  } finally {
    statusLoading.value = false
  }
}

watch(selectedMonth, async () => {
  detailPage.value = 1
  data.value = undefined
  details.value = undefined
  editing.value = false
  cancelStaffingAnalysisEdit()
  cancelStaffingInputsEdit()
  shippingSelectedRows.value = []
  shippingChartVisible.value = false
  shippingChartRows.value = []
  await refreshActive()
})
watch(activeTab, async () => {
  detailPage.value = 1
  details.value = undefined
  shippingChartVisible.value = false
  shippingChartRows.value = []
  cancelStaffingAnalysisEdit()
  cancelStaffingInputsEdit()
  if (activeTab.value !== 'summary') await loadDetails()
})
onMounted(async () => {
  detailTypes.value = await getAnalyticsDetailTypes()
  await load()
})
</script>

<template>
  <div class="page-heading">
    <div><h1>经营分析</h1><p>核心经营指标、月度变化、趋势与复盘统一管理。</p></div>
    <div class="heading-actions">
      <ElDatePicker v-model="selectedMonth" type="month" value-format="YYYY-MM" format="YYYY年MM月" :clearable="false" />
      <ElButton :icon="Refresh" @click="refreshActive">刷新</ElButton>
      <ElButton v-if="activeTab === 'summary' && !editing && canManage" type="primary" :icon="EditPen" @click="beginEditing">编辑本月</ElButton>
      <template v-else-if="activeTab === 'summary' && editing">
        <ElButton @click="editing = false; resetEditor()">取消</ElButton>
        <ElButton type="primary" :icon="Check" :loading="saving" @click="save">保存</ElButton>
      </template>
      <ElButton
        v-if="activeTab === 'summary' && !editing && data?.review.status === 'draft' && auth.can('analytics.manage')"
        :icon="CircleCheck"
        :loading="statusLoading"
        @click="changeStatus('completed')"
      >标记完成</ElButton>
      <ElButton
        v-if="activeTab === 'summary' && !editing && data?.review.status === 'completed' && auth.can('analytics.manage')"
        :icon="Lock"
        :loading="statusLoading"
        @click="changeStatus('archived')"
      >归档本月</ElButton>
      <ElButton
        v-if="activeTab === 'summary' && !editing && isArchived && auth.isSystemAdmin"
        :icon="Unlock"
        :loading="statusLoading"
        @click="changeStatus('draft')"
      >重新开启</ElButton>
    </div>
  </div>

  <ElTabs v-model="activeTab" class="analysis-tabs">
    <ElTabPane label="月度总表" name="summary" />
    <ElTabPane v-for="item in detailTypes" :key="item.code" :label="item.name" :name="item.code" />
  </ElTabs>

  <template v-if="activeTab === 'summary'">
    <section class="surface-card month-status-card">
      <div class="status-main">
        <div class="status-title">
          <ElTag :type="statusInfo.type" effect="light">{{ statusInfo.label }}</ElTag>
          <strong>{{ selectedMonth }} 经营分析</strong>
          <span>{{ statusInfo.hint }}</span>
        </div>
        <div class="status-update">
          <span>最近更新</span>
          <strong>{{ formatActivity(data?.latest_activity?.updated_at) }}</strong>
          <small>{{ data?.latest_activity?.updated_by_name || data?.latest_activity?.source || '系统历史数据' }}</small>
        </div>
      </div>
      <div class="completion-row">
        <div class="completion-copy">
          <strong>数据完成度 {{ data?.completion.completed ?? 0 }}/{{ data?.completion.total ?? 0 }}</strong>
          <span>自动取数和人工上传可以并行，点击项目可直接补充对应分表。</span>
        </div>
        <ElProgress :percentage="data?.completion.percent ?? 0" :stroke-width="8" />
      </div>
      <div class="completion-items">
        <button
          v-for="item in data?.completion.items"
          :key="item.code"
          type="button"
          :class="['completion-item', item.state]"
          @click="openDataset(item.code)"
        >
          <span>{{ item.name }}</span>
          <strong>{{ item.label }}</strong>
          <small v-if="item.source_name">{{ item.source_name }}</small>
        </button>
      </div>
      <p class="independent-note">系统内独立保存，不会回写企业微信原表。</p>
    </section>

    <section v-loading="loading" class="surface-card review-matrix-card">
      <div class="card-heading matrix-heading">
        <div>
          <h3>月度经营复盘总表</h3>
          <p>与上方月份联动，仅展示当前选择月份的数据、变化情况和原因。</p>
        </div>
        <div class="matrix-legend">
          <span><i class="ready" /> 已有数据</span>
          <span><i /> 待补取数</span>
        </div>
      </div>
      <div class="review-matrix-scroll">
        <table class="review-matrix" :style="{ minWidth: `${reviewMatrixWidth}px` }">
          <colgroup>
            <col class="matrix-category-col">
            <col class="matrix-detail-col">
            <col v-for="month in reviewMonths" :key="`col-${month}`" class="matrix-month-col">
            <col class="matrix-change-col">
            <col class="matrix-ratio-col">
            <col class="matrix-reason-col">
          </colgroup>
          <thead>
            <tr>
              <th class="matrix-sticky matrix-category-head">板块</th>
              <th class="matrix-sticky matrix-detail-head">细项</th>
              <th
                v-for="month in reviewMonths"
                :key="month"
                :class="{ 'is-current': month === selectedMonth }"
              >{{ matrixMonthLabel(month) }}</th>
              <th class="matrix-summary-head">{{ selectedMonthLabel }}<br>变化数量</th>
              <th class="matrix-summary-head">{{ selectedMonthLabel }}<br>数量变化占比</th>
              <th class="matrix-summary-head">{{ selectedMonthLabel }}变化数量变化原因</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="group in reviewMatrix" :key="group.category">
              <tr v-for="(row, rowIndex) in group.rows" :key="row.code">
                <th
                  v-if="rowIndex === 0"
                  :rowspan="group.rows.length"
                  class="matrix-category-cell matrix-sticky"
                >{{ group.category }}</th>
                <th class="matrix-detail-cell matrix-sticky">
                  <button
                    v-if="row.detailCode"
                    type="button"
                    class="matrix-detail-link"
                    @click="openDataset(row.detailCode)"
                  >{{ row.label }}</button>
                  <span v-else>{{ row.label }}</span>
                  <small :class="{ ready: row.metric?.value !== null && row.metric?.value !== undefined }">
                    {{ row.metric?.value !== null && row.metric?.value !== undefined ? row.metric?.source_label : '待补取数' }}
                  </small>
                </th>
                <td
                  v-for="month in reviewMonths"
                  :key="`${row.code}-${month}`"
                  :class="['matrix-number-cell', { 'is-current': month === selectedMonth }]"
                >
                  <ElInputNumber
                    v-if="editing && month === selectedMonth && row.metric"
                    v-model="editValues[row.metric.id]"
                    :precision="row.metric.precision"
                    :controls="false"
                  />
                  <template v-else>{{ formatMatrixNumber(matrixValue(row.code, month), row.metric) }}</template>
                </td>
                <td class="matrix-number-cell matrix-change-cell">
                  {{ formatMatrixNumber(matrixChange(row), row.metric) }}
                </td>
                <td class="matrix-number-cell matrix-ratio-cell">{{ formatMatrixRatio(row) }}</td>
                <td class="matrix-reason-cell">
                  <ElInput
                    v-if="editing && row.metric"
                    v-model="editNotes[row.metric.id]"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 3 }"
                    maxlength="500"
                    placeholder="填写变化原因或说明"
                  />
                  <span v-else :class="{ placeholder: !row.metric?.note }">{{ row.metric?.note || '待补充' }}</span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

  <div class="analysis-grid">
    <section class="surface-card trend-card" v-loading="loading">
      <div class="card-heading"><div><h3>业务趋势</h3><p>已迁移月份的发货与退货走势</p></div></div>
      <VChart :option="trendOption" autoresize class="trend-chart" />
    </section>
    <section class="surface-card review-card">
      <div class="card-heading"><div><h3>月度复盘</h3><p>{{ selectedMonth }} 结论与下月重点</p></div><ElTag :type="statusInfo.type" effect="plain">{{ statusInfo.label }}</ElTag></div>
      <div v-if="editing" class="review-editor">
        <label><span>整体结论</span><ElInput v-model="summary" type="textarea" :rows="3" placeholder="概括本月经营情况" /></label>
        <label><span>经营亮点</span><ElInput v-model="highlights" type="textarea" :rows="2" placeholder="本月做得好的事项" /></label>
        <label><span>主要问题及原因</span><ElInput v-model="issues" type="textarea" :rows="2" placeholder="问题、异常及初步原因" /></label>
        <label><span>风险与协同事项</span><ElInput v-model="risks" type="textarea" :rows="2" placeholder="需要关注或协同解决的事项" /></label>
        <label><span>下月重点工作</span><ElInput v-model="nextPlan" type="textarea" :rows="2" placeholder="下月需要推进的重点" /></label>
      </div>
      <div v-else class="review-copy">
        <p class="review-summary">{{ data?.review.summary || '本月整体复盘尚未录入，可点击“编辑本月”补充。' }}</p>
        <dl v-if="reviewSections.length" class="review-sections">
          <template v-for="section in reviewSections" :key="section.label">
            <dt>{{ section.label }}</dt>
            <dd>{{ section.value }}</dd>
          </template>
        </dl>
      </div>
      <div v-if="data?.events.length" class="event-list">
        <div v-for="event in data.events" :key="event.id"><ElTag size="small" effect="plain">{{ event.category }}</ElTag><strong>{{ event.title }}</strong><p>{{ event.description }}</p></div>
      </div>
    </section>
  </div>

  </template>

  <section v-else v-loading="detailLoading" class="surface-card detail-card">
    <div class="detail-heading">
      <div class="detail-heading-copy">
        <div class="detail-title-row">
          <h3>{{ currentDetailType?.name }}</h3>
          <div v-if="isSystemDataset" class="shipping-headline-stat">
            <span>当月{{ systemMetricLabel }}</span>
            <strong>{{ formatCount(systemSummaryTotal) }}</strong>
            <small>{{ systemMetricUnit }}</small>
          </div>
          <ElButton
            v-if="isSystemDataset"
            class="shipping-chart-button"
            type="primary"
            :icon="TrendCharts"
            :loading="shippingChartLoading"
            :disabled="!(details?.total ?? 0)"
            @click="openSystemCharts"
          >图表分析</ElButton>
          <ElTag
            v-if="isSystemDataset && details?.snapshot"
            class="shipping-snapshot-tag"
            :type="shippingSnapshotTagType(details.snapshot.state)"
            effect="plain"
          >
            <ElIcon v-if="details.snapshot.state === 'historical'"><Lock /></ElIcon>
            {{ details.snapshot.label }}
          </ElTag>
        </div>
        <p>{{ currentDetailType?.description }}</p>
      </div>
      <div class="detail-actions">
        <ElTag v-if="isArchived" type="info" effect="plain"><ElIcon><Lock /></ElIcon> 本月已归档</ElTag>
        <ElButton
          v-if="isSystemDataset && canManage && details?.snapshot?.can_system_sync"
          type="success"
          :icon="Refresh"
          :loading="systemPreviewLoading"
          @click="openSystemPreview"
        >系统取数</ElButton>
        <ElTooltip
          v-else-if="isSystemDataset && canManage && details?.snapshot"
          :content="details.snapshot.hint"
          placement="top"
        >
          <span><ElButton :icon="Lock" disabled>{{ details.snapshot.label }}</ElButton></span>
        </ElTooltip>
        <ElDropdown v-if="!detailManagement" trigger="click" @command="handleExcelCommand">
          <ElButton :icon="UploadFilled" :loading="previewLoading || staffingExportLoading">
            Excel 操作 <ElIcon class="el-icon--right"><ArrowDown /></ElIcon>
          </ElButton>
          <template #dropdown>
            <ElDropdownMenu>
              <ElDropdownItem command="download" :icon="Download">下载匹配模板</ElDropdownItem>
              <ElDropdownItem v-if="canManage" command="upload" :icon="UploadFilled">上传 Excel 更新</ElDropdownItem>
              <ElDropdownItem v-if="activeTab === 'staffing'" command="export" :icon="Download" divided>导出当前数据</ElDropdownItem>
            </ElDropdownMenu>
          </template>
        </ElDropdown>
        <ElButton
          v-if="detailManagement"
          type="primary"
          plain
          :icon="OfficeBuilding"
          @click="router.push(detailManagement.route)"
        >{{ detailManagement.label }}</ElButton>
        <ElButton
          v-if="isSystemDataset"
          type="primary"
          plain
          :icon="Download"
          :disabled="!(details?.total ?? 0)"
          :loading="activeTab === 'return_items' && returnExportLoading"
          @click="activeTab === 'shipping_orders' ? openShippingExport() : exportReturnData()"
        >导出数据</ElButton>
        <input
          ref="detailFileInput"
          class="native-file-input"
          type="file"
          accept=".xlsx"
          @change="onNativeDetailFile"
        />
      </div>
    </div>

    <ElAlert
      class="detail-hint"
      type="info"
      :closable="false"
      show-icon
    >
      <template #title>
        <div class="detail-context-row">
          <span class="detail-context-copy">{{ currentDetailType?.summary_hint || '' }}</span>
          <div v-if="details?.batches.length" class="detail-context-source">
            <span>当前数据来源</span>
            <div class="batch-tags">
              <ElTag v-for="batch in details.batches" :key="`${batch.original_name}-${batch.imported_at}`" effect="plain">
                {{ batch.original_name }} · {{ batch.row_count }} 行 · {{ batch.imported_by_name || '历史导入' }} · {{ formatImportedAt(batch.imported_at) }}
              </ElTag>
            </div>
          </div>
        </div>
      </template>
    </ElAlert>

    <ElAlert
      v-if="activeTab === 'staffing' && details?.is_template"
      class="staffing-template-alert"
      type="warning"
      :closable="false"
      show-icon
    >
      <template #title>
        <strong>本月尚未维护，已展示人员调整填写框架</strong>
      </template>
      <p>点击带编辑图标的四项基础值进行填写；首次保存后建立本月数据，配置、效率和环比指标由系统自动计算。</p>
    </ElAlert>

    <div v-if="activeTab === 'staffing'" class="staffing-kpis">
      <article
        v-for="card in staffingSummaryCards"
        :key="card.label"
        :class="`tone-${card.tone}`"
      >
        <span>{{ card.label }}</span>
        <strong>{{ formatCount(card.value) }}</strong>
        <small>{{ card.unit }}</small>
      </article>
    </div>

    <div v-else-if="!isSystemDataset" class="detail-stats">
      <div><span>有效明细</span><strong>{{ details?.total ?? 0 }} 行</strong></div>
      <div><span>{{ activeTab === 'shipping_orders' ? '数据批次' : '导入批次' }}</span><strong>{{ details?.batches.length ?? 0 }} 个</strong></div>
      <div v-for="(value, code) in details?.summary" :key="code">
        <span>自动汇总 · {{ metricName(code) }}</span><strong>{{ formatCount(value) }}</strong>
      </div>
    </div>

    <div v-if="isSystemDataset" class="shipping-table-toolbar">
      <ElInput
        v-if="activeTab === 'shipping_orders'"
        v-model="shippingTeamSearch"
        :prefix-icon="Search"
        clearable
        placeholder="搜索团队名称"
        aria-label="搜索团队名称"
        @input="scheduleShippingSearch"
      />
      <ElInput
        v-else
        v-model="returnTeamSearch"
        :prefix-icon="Search"
        clearable
        placeholder="搜索团队名称"
        aria-label="搜索退货团队名称"
        @input="scheduleReturnSearch"
      />
      <span>
        当前匹配 <strong>{{ details?.total ?? 0 }}</strong> 个团队
        <i>点击“{{ activeTab === 'return_items' ? '退货件数合计' : '发货单量' }}”表头可排序</i>
      </span>
    </div>
    <div v-else-if="activeTab === 'staffing'" class="staffing-table-toolbar">
      <ElInput
        v-model="staffingTeamSearch"
        :prefix-icon="Search"
        clearable
        placeholder="搜索小组"
        aria-label="搜索人员调整小组"
        @input="scheduleStaffingSearch"
      />
      <span>
        {{ details?.is_template ? '模板包含' : '当前匹配' }}
        <strong>{{ details?.total ?? 0 }}</strong> 个小组
        <i>{{ details?.is_template ? '填写基础值后自动计算其余指标' : '派生指标均由系统按月计算' }}</i>
      </span>
    </div>

    <ElTable
      v-if="visibleDetailColumns.length"
      :data="details?.rows ?? []"
      border
      stripe
      :class="['detail-table', {
        'shipping-detail-table': isSystemDataset,
        'staffing-detail-table': activeTab === 'staffing',
      }]"
      :header-row-class-name="isSystemDataset ? 'shipping-table-header' : ''"
      row-key="id"
      @selection-change="onShippingSelectionChange"
      @sort-change="changeDetailSort"
    >
      <ElTableColumn
        v-if="activeTab === 'shipping_orders'"
        type="selection"
        width="52"
        fixed="left"
        reserve-selection
      />
      <ElTableColumn type="index" label="序号" width="72" fixed="left" :index="detailRowIndex" />
      <ElTableColumn
        v-for="column in visibleDetailColumns"
        :key="column"
        :prop="column"
        :label="column"
        :fixed="activeTab === 'staffing' && column === '小组' ? 'left' : undefined"
        :min-width="detailColumnWidth(column)"
        :align="detailColumnAlign(column)"
        :sortable="activeTab === 'shipping_orders' && column === '发货单量'
          ? 'custom'
          : activeTab === 'return_items' && column === '退货件数合计'
            ? 'custom'
          : activeTab === 'staffing' && !['小组', '综合分析'].includes(column)"
        :show-overflow-tooltip="activeTab !== 'staffing'
          || (!['综合分析'].includes(column) && !isStaffingEditableColumn(column))"
      >
        <template #header>
          <span :class="['staffing-column-header', { editable: activeTab === 'staffing' && isStaffingEditableColumn(column) }]">
            {{ column }}
            <ElIcon v-if="activeTab === 'staffing' && isStaffingEditableColumn(column)"><EditPen /></ElIcon>
          </span>
        </template>
        <template #default="{ row }">
          <strong v-if="activeTab === 'shipping_orders' && column === '数据发货占比'">
            {{ displayShippingShare(row.values[column]) }}
          </strong>
          <strong v-else-if="activeTab === 'return_items' && column === '数据退货占比'">
            {{ displayShippingShare(row.values[column]) }}
          </strong>
          <strong v-else-if="activeTab === 'return_items' && returnCountColumns.has(column)">
            {{ formatCount(Number(row.values[column] ?? 0)) }}
          </strong>
          <div
            v-else-if="activeTab === 'staffing' && column === '小组'"
            class="staffing-team-cell"
          >
            <span>{{ displayColumnValue(column, row.values[column]) }}</span>
            <div v-if="staffingInputsEditingId === row.id">
              <ElButton
                size="small"
                :disabled="staffingInputsSavingId === row.id"
                @click="cancelStaffingInputsEdit"
              >取消</ElButton>
              <ElButton
                size="small"
                type="primary"
                :icon="Check"
                :loading="staffingInputsSavingId === row.id"
                @click="saveStaffingInputs(row)"
              >保存</ElButton>
            </div>
          </div>
          <div
            v-else-if="activeTab === 'staffing' && column === '综合分析'"
            class="staffing-analysis-cell"
          >
            <template v-if="staffingAnalysisEditingId === row.id">
              <div class="staffing-analysis-editor">
                <label v-for="(heading, index) in staffingAnalysisHeadings" :key="heading">
                  <span><b>{{ index + 1 }}</b>{{ heading }}</span>
                  <ElInput
                    v-model="staffingAnalysisDraft[index]"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 8 }"
                    :maxlength="1500"
                    :placeholder="`填写${heading}`"
                  />
                </label>
                <div class="staffing-analysis-actions">
                  <ElButton size="small" @click="cancelStaffingAnalysisEdit">取消</ElButton>
                  <ElButton
                    size="small"
                    type="primary"
                    :icon="Check"
                    :loading="staffingAnalysisSavingId === row.id"
                    @click="saveStaffingAnalysis(row)"
                  >保存</ElButton>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="staffing-analysis-readonly">
                <div class="staffing-analysis-heading">
                  <span>三项复盘</span>
                  <ElButton
                    v-if="canManage"
                    text
                    type="primary"
                    size="small"
                    :icon="EditPen"
                    @click="beginStaffingAnalysisEdit(row)"
                  >编辑</ElButton>
                </div>
                <article
                  v-for="(section, index) in staffingAnalysisSections(row.values[column])"
                  :key="section.heading"
                  :class="{ empty: !section.text }"
                >
                  <b>{{ index + 1 }}</b>
                  <div>
                    <strong>{{ section.heading }}</strong>
                    <p>{{ section.text || '待补充' }}</p>
                  </div>
                </article>
              </div>
            </template>
          </div>
          <div
            v-else-if="activeTab === 'staffing' && isStaffingEditableColumn(column)"
            class="staffing-editable-cell"
          >
            <ElInputNumber
              v-if="staffingInputsEditingId === row.id"
              :model-value="staffingInputDraftValue(column)"
              :min="0"
              :max="['正式工人数', '最优配置'].includes(column) ? 1000000 : 1000000000"
              :precision="2"
              :step="1"
              :controls="false"
              size="small"
              :aria-label="`修改${column}`"
              @update:model-value="updateStaffingInputDraft(column, $event)"
              @keyup.enter="saveStaffingInputs(row)"
            />
            <button
              v-else-if="canManage"
              type="button"
              :aria-label="`编辑${column}`"
              :disabled="staffingInputsEditingId !== undefined && staffingInputsEditingId !== row.id"
              @click="beginStaffingInputsEdit(row)"
            >
              <span>{{ displayColumnValue(column, row.values[column]) }}</span>
              <ElIcon><EditPen /></ElIcon>
            </button>
            <span v-else>{{ displayColumnValue(column, row.values[column]) }}</span>
          </div>
          <ElTag
            v-else-if="activeTab === 'staffing' && column === '配置偏差'"
            :type="staffingGapTagType(row.values[column])"
            effect="light"
            round
          >{{ staffingGapLabel(row.values[column]) }}</ElTag>
          <span
            v-else-if="activeTab === 'staffing' && ['效率差额', '人均月产出净变化'].includes(column)"
            :class="['staffing-delta', {
              positive: Number(row.values[column]) > 0,
              negative: Number(row.values[column]) < 0,
            }]"
          >{{ displayColumnValue(column, row.values[column]) }}</span>
          <span v-else>{{ displayColumnValue(column, row.values[column]) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        v-if="activeTab === 'shipping_orders'"
        prop="消费金额"
        label="消费金额"
        min-width="160"
        align="right"
      >
        <template #default="{ row }">
          <span class="shipping-consumption-amount">{{ displayConsumptionAmount(row.values.消费金额) }}</span>
        </template>
      </ElTableColumn>
      <ElTableColumn
        v-if="activeTab !== 'shipping_orders' && activeTab !== 'return_items' && activeTab !== 'staffing'"
        label="数据来源"
        min-width="210"
        fixed="right"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ row.source_name }}</template>
      </ElTableColumn>
    </ElTable>
    <ElEmpty
      v-else
      :description="isSystemDataset
        ? details?.snapshot?.state === 'historical'
          ? '该月份暂无可用历史快照，系统不会再自动覆盖'
          : details?.snapshot?.state === 'future'
            ? '未来月份暂不允许系统取数'
            : '该月份尚未系统取数，可点击“系统取数”获取'
        : detailManagement
          ? `该月份暂无${currentDetailType?.name || ''}，请到${detailManagement.label}模块维护`
          : '该月份尚未上传分表数据，可下载模板后导入'"
    />
    <ElPagination
      v-if="(details?.total ?? 0) > 0"
      class="detail-pagination"
      background
      layout="total, sizes, prev, pager, next, jumper"
      :current-page="detailPage"
      :page-size="detailPageSize"
      :page-sizes="[50, 100, 200]"
      :pager-count="5"
      :total="details?.total ?? 0"
      @current-change="changeDetailPage"
      @size-change="changeDetailPageSize"
    />
  </section>

  <ElDrawer
    v-model="shippingChartVisible"
    class="shipping-chart-drawer"
    size="min(1280px, 96vw)"
    destroy-on-close
  >
    <template #header>
      <div class="shipping-chart-header">
        <div>
          <span>{{ chartIsReturn ? 'RETURN ANALYTICS' : 'SHIPPING ANALYTICS' }}</span>
          <h2>{{ selectedMonthLabel }}{{ chartMetricLabel }}图表分析</h2>
          <p>{{ chartIsReturn ? '团队退货排名、构成拆解、集中度与历史趋势' : '团队排名、发货结构、集中度与历史趋势' }}</p>
        </div>
        <ElTag v-if="chartSearchText" type="primary" effect="plain">
          当前搜索：{{ chartSearchText }}
        </ElTag>
      </div>
    </template>

    <div v-loading="shippingChartLoading" class="shipping-chart-panel">
      <template v-if="shippingChartTeams.length">
        <div class="shipping-chart-kpis">
          <article class="primary">
            <span>{{ chartIsReturn ? '退货件数合计' : '发货总量' }}</span>
            <strong>{{ formatCount(shippingChartStats.total) }}</strong>
            <small>{{ chartMetricUnit }} · 当前筛选范围</small>
          </article>
          <article>
            <span>团队数量</span>
            <strong>{{ shippingChartStats.teamCount }}</strong>
            <small>个有效团队</small>
          </article>
          <article>
            <span>团队平均</span>
            <strong>{{ formatCount(Math.round(shippingChartStats.average)) }}</strong>
            <small>{{ chartMetricUnit }} / 团队</small>
          </article>
          <article>
            <span>头部团队</span>
            <strong class="team-name">{{ shippingChartStats.topTeam?.name || '—' }}</strong>
            <small>{{ formatCount(shippingChartStats.topTeam?.value ?? 0) }} {{ chartMetricUnit }} · {{ (shippingChartStats.topTeam?.share ?? 0).toFixed(2) }}%</small>
          </article>
          <article>
            <span>TOP 5 集中度</span>
            <strong>{{ shippingChartStats.topFiveShare.toFixed(2) }}%</strong>
            <small>前五团队贡献占比</small>
          </article>
        </div>

        <div class="shipping-chart-grid">
          <article class="shipping-chart-card ranking-card">
            <div class="shipping-chart-title">
              <div><strong>团队{{ chartMetricLabel }} TOP 12</strong><span>按{{ chartMetricLabel }}从高到低排列</span></div>
              <ElTag effect="plain">单位：{{ chartMetricUnit }}</ElTag>
            </div>
            <VChart :option="shippingRankingOption" autoresize class="shipping-ranking-chart" />
          </article>

          <article class="shipping-chart-card share-card">
            <div class="shipping-chart-title">
              <div><strong>团队{{ chartMetricLabel }}结构</strong><span>头部团队与其他团队占比</span></div>
            </div>
            <VChart :option="shippingShareOption" autoresize class="shipping-share-chart" />
          </article>

          <article class="shipping-chart-card trend-detail-card">
            <div class="shipping-chart-title">
              <div><strong>月度{{ chartMetricLabel }}趋势</strong><span>最近 12 个月{{ chartMetricLabel }}走势</span></div>
            </div>
            <VChart :option="shippingVolumeTrendOption" autoresize class="shipping-trend-detail-chart" />
          </article>

          <article class="shipping-chart-card concentration-card">
            <div class="shipping-chart-title">
              <div><strong>头部团队贡献</strong><span>TOP 8 团队占比与数量</span></div>
            </div>
            <div class="concentration-list">
              <div v-for="(team, index) in shippingChartTeams.slice(0, 8)" :key="team.name">
                <span class="rank">{{ index + 1 }}</span>
                <div class="team-copy">
                  <strong>{{ team.name }}</strong>
                  <ElProgress :percentage="Number(team.share.toFixed(2))" :show-text="false" :stroke-width="7" />
                </div>
                <div class="team-number">
                  <strong>{{ formatCount(team.value) }}</strong>
                  <span>{{ team.share.toFixed(2) }}%</span>
                </div>
              </div>
            </div>
          </article>

          <article v-if="chartIsReturn" class="shipping-chart-card return-component-card">
            <div class="shipping-chart-title">
              <div><strong>退货构成拆解 TOP 10</strong><span>处理退货、拦截扣费与异常扣费的团队构成</span></div>
              <ElTag effect="plain">单位：件</ElTag>
            </div>
            <VChart :option="returnComponentOption" autoresize class="return-component-chart" />
          </article>
        </div>

        <div class="shipping-chart-insight">
          <strong>结构提示</strong>
          <span>
            {{ chartMetricLabel }}中位数为 {{ formatCount(Math.round(shippingChartStats.median)) }} {{ chartMetricUnit }}；
            头部团队贡献 {{ (shippingChartStats.topTeam?.share ?? 0).toFixed(2) }}%，
            前五团队合计贡献 {{ shippingChartStats.topFiveShare.toFixed(2) }}%。
          </span>
        </div>
      </template>
      <ElEmpty v-else-if="!shippingChartLoading" :description="`当前月份或搜索范围暂无可展示的${chartMetricLabel}数据`" />
    </div>
  </ElDrawer>

  <ElDialog v-model="exportVisible" title="导出发货数据" width="560px" destroy-on-close>
    <div class="export-config">
      <div class="export-config-section">
        <strong>导出范围</strong>
        <ElRadioGroup v-model="exportScope" class="export-scope-group">
          <ElRadio value="filtered">
            当前筛选结果（{{ details?.total ?? 0 }} 个团队）
          </ElRadio>
          <ElRadio value="selected" :disabled="!shippingSelectedRows.length">
            已勾选团队（{{ shippingSelectedRows.length }} 个）
          </ElRadio>
        </ElRadioGroup>
      </div>
      <div class="export-config-section">
        <strong>导出字段</strong>
        <ElCheckboxGroup v-model="exportColumns" class="export-column-grid">
          <ElCheckbox value="团队名称">团队名称</ElCheckbox>
          <ElCheckbox value="发货单量">发货单量</ElCheckbox>
          <ElCheckbox value="数据发货占比">数据发货占比</ElCheckbox>
        </ElCheckboxGroup>
        <small>序号会自动生成；当前搜索条件和发货单量排序会保留到导出文件。</small>
      </div>
    </div>
    <template #footer>
      <ElButton @click="exportVisible = false">取消</ElButton>
      <ElButton type="primary" :loading="exportLoading" @click="commitShippingExport">
        确认导出
      </ElButton>
    </template>
  </ElDialog>

  <ElDialog
    v-model="systemPreviewVisible"
    :title="`系统取数预览 · ${systemMetricLabel}`"
    :width="activeTab === 'return_items' ? '1050px' : '760px'"
    destroy-on-close
  >
    <div v-if="activeSystemPreview" class="preview-panel system-preview">
      <ElAlert
        type="info"
        :closable="false"
        show-icon
        title="远程业务库仅执行只读查询，确认后只保存到经营分析系统。"
      />
      <ElAlert
        v-for="warning in activeSystemPreview.warnings"
        :key="warning"
        class="preview-warning"
        :type="activeSystemPreview.blocking ? 'error' : 'warning'"
        :closable="false"
        show-icon
        :title="warning"
      />
      <div class="system-source-grid">
        <div><span>页面月份</span><strong>{{ selectedMonth }}</strong></div>
        <div><span>统计区间</span><strong>{{ activeSystemPreview.month_start }} 至 {{ activeSystemPreview.month_end }}（不含）</strong></div>
        <div><span>来源表</span><strong>{{ activeSystemPreview.source_name }}</strong></div>
        <div><span>团队数量</span><strong>{{ activeSystemPreview.row_count }} 个</strong></div>
        <div><span>{{ systemMetricLabel }}</span><strong>{{ formatCount(activeSystemPreview.total) }} {{ systemMetricUnit }}</strong></div>
      </div>
      <div class="condition-list">
        <span>取值条件</span>
        <ElTag v-for="condition in activeSystemPreview.conditions" :key="condition" effect="plain">{{ condition }}</ElTag>
      </div>
      <ElTable :data="activeSystemPreview.rows" border stripe max-height="390">
        <ElTableColumn prop="团队名称" label="团队名称" min-width="180" />
        <ElTableColumn
          v-if="activeTab === 'shipping_orders'"
          prop="发货单量"
          label="发货单量"
          min-width="180"
          align="right"
        >
          <template #default="{ row }"><strong>{{ formatCount(row.发货单量) }}</strong></template>
        </ElTableColumn>
        <ElTableColumn
          v-if="activeTab === 'shipping_orders'"
          prop="数据发货占比"
          label="数据发货占比"
          min-width="150"
          align="right"
        >
          <template #default="{ row }"><strong>{{ displayShippingShare(row.数据发货占比) }}</strong></template>
        </ElTableColumn>
        <template v-else>
          <ElTableColumn prop="处理退货件数" label="处理退货件数" min-width="145" align="right">
            <template #default="{ row }">{{ formatCount(row.处理退货件数) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="拦截件扣费件数" label="拦截件扣费件数" min-width="155" align="right">
            <template #default="{ row }">{{ formatCount(row.拦截件扣费件数) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="异常件扣费件数" label="异常件扣费件数" min-width="155" align="right">
            <template #default="{ row }">{{ formatCount(row.异常件扣费件数) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="退货件数合计" label="退货件数合计" min-width="145" align="right">
            <template #default="{ row }"><strong>{{ formatCount(row.退货件数合计) }}</strong></template>
          </ElTableColumn>
          <ElTableColumn prop="数据退货占比" label="数据退货占比" min-width="145" align="right">
            <template #default="{ row }"><strong>{{ displayShippingShare(row.数据退货占比) }}</strong></template>
          </ElTableColumn>
        </template>
      </ElTable>
      <ElAlert
        class="replace-warning"
        type="warning"
        :closable="false"
        show-icon
        :title="`确认保存后，将替换该月份${systemMetricLabel}分表的当前有效数据；历史批次仍保留。`"
      />
    </div>
    <template #footer>
      <ElButton @click="systemPreviewVisible = false">取消</ElButton>
      <ElButton
        type="primary"
        :loading="systemSyncing"
        :disabled="activeSystemPreview?.blocking"
        @click="commitSystemData"
      >确认保存到系统</ElButton>
    </template>
  </ElDialog>

  <ElDialog v-model="previewVisible" :title="`导入预览 · ${currentDetailType?.name || ''}`" width="88%" destroy-on-close>
    <div v-if="importPreview" class="preview-panel">
      <div class="preview-meta">
        <span>文件：<strong>{{ importPreview.original_name }}</strong></span>
        <span>工作表：<strong>{{ importPreview.sheet_name }}</strong></span>
        <span>共 <strong>{{ importPreview.row_count }}</strong> 行</span>
      </div>
      <ElAlert
        v-for="warning in importPreview.warnings"
        :key="warning"
        class="preview-warning"
        type="warning"
        :closable="false"
        show-icon
        :title="warning"
      />
      <div v-if="Object.keys(importPreview.summary).length" class="preview-summary">
        <span>导入后预计更新总表：</span>
        <ElTag v-for="(value, code) in importPreview.summary" :key="code" type="success" effect="plain">
          {{ metricName(code) }} {{ formatCount(value) }}
        </ElTag>
      </div>
      <ElAlert
        v-if="activeTab === 'shipping_orders' && importPreview.match_result"
        class="preview-warning"
        type="success"
        :closable="false"
        show-icon
        :title="`按团队名称匹配：${importPreview.match_result.matched_count} 个成功，${importPreview.match_result.unmatched_count} 个未匹配`"
      />
      <ElAlert
        v-else-if="activeTab === 'staffing' && importPreview.match_result"
        class="preview-warning"
        type="success"
        :closable="false"
        show-icon
        :title="`按小组匹配：更新 ${importPreview.match_result.matched_count} 组，新增 ${importPreview.match_result.added_count ?? 0} 组，保留未上传的 ${importPreview.match_result.preserved_count ?? 0} 组`"
      />
      <ElTable :data="importPreview.rows" border stripe max-height="430">
        <ElTableColumn v-if="!importPreview.columns.includes('序号')" type="index" label="#" width="56" fixed="left" />
        <ElTableColumn
          v-for="column in importPreview.columns"
          :key="column"
          :label="column"
          min-width="150"
          show-overflow-tooltip
        >
          <template #default="{ row }">{{ displayColumnValue(column, row[column]) }}</template>
        </ElTableColumn>
      </ElTable>
      <p v-if="importPreview.row_count > importPreview.rows.length" class="preview-note">
        这里只展示前 {{ importPreview.rows.length }} 行，确认后会导入全部 {{ importPreview.row_count }} 行。
      </p>
    </div>
    <template #footer>
      <div class="preview-footer">
        <div v-if="['shipping_orders', 'staffing'].includes(activeTab)">
          <span>导入方式</span>
          <ElTag type="primary" effect="plain">
            {{ activeTab === 'staffing' ? '按页面月份和小组匹配，保留历史版本' : '按团队名称匹配更新' }}
          </ElTag>
        </div>
        <div v-else>
          <span>导入方式</span>
          <ElRadioGroup v-model="importMode">
            <ElRadioButton value="replace">覆盖当月</ElRadioButton>
            <ElRadioButton value="append">追加数据</ElRadioButton>
          </ElRadioGroup>
        </div>
        <div>
          <ElButton @click="previewVisible = false">取消</ElButton>
          <ElButton type="primary" :loading="importing" @click="commitImport">确认导入系统</ElButton>
        </div>
      </div>
    </template>
  </ElDialog>
</template>

<style scoped>
.heading-actions { display:flex; align-items:center; gap:9px; }
.analysis-tabs { margin-bottom:18px; }
.analysis-tabs :deep(.el-tabs__header) { margin-bottom:0; }
.month-status-card { margin-bottom:20px; padding:20px 22px 16px; }
.status-main,.completion-row { display:flex; align-items:center; justify-content:space-between; gap:24px; }
.status-title { display:flex; align-items:center; flex-wrap:wrap; gap:10px; }
.status-title strong { color:#1c2b45; font-size:16px; }
.status-title span { color:#7e8a9e; font-size:11px; }
.status-update { display:grid; min-width:210px; grid-template-columns:auto 1fr; column-gap:8px; text-align:right; }
.status-update span,.status-update small { color:#8995a7; font-size:10px; }
.status-update strong { color:#33425b; font-size:11px; }
.status-update small { grid-column:1/-1; margin-top:3px; }
.completion-row { margin-top:17px; padding-top:16px; border-top:1px solid #edf0f5; }
.completion-copy { min-width:330px; }
.completion-copy strong { display:block; color:#263650; font-size:13px; }
.completion-copy span { display:block; margin-top:4px; color:#8995a7; font-size:10px; }
.completion-row :deep(.el-progress) { width:min(480px,48%); }
.completion-items { display:grid; margin-top:14px; grid-template-columns:repeat(8,minmax(105px,1fr)); gap:8px; }
.completion-item { min-width:0; padding:10px 11px; border:1px solid #e7ebf1; border-radius:9px; color:#67758b; background:#fafbfd; text-align:left; cursor:pointer; transition:.16s ease; }
.completion-item:hover { border-color:#9bbcf4; background:#f4f8ff; transform:translateY(-1px); }
.completion-item span,.completion-item strong,.completion-item small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.completion-item span { font-size:11px; }
.completion-item strong { margin-top:4px; color:#3c4c65; font-size:10px; }
.completion-item small { margin-top:3px; color:#9aa4b3; font-size:9px; }
.completion-item.system { border-color:#bfe5da; background:#f1fbf7; }.completion-item.system strong { color:#21806a; }
.completion-item.uploaded { border-color:#cfead9; background:#f4fbf6; }.completion-item.uploaded strong { color:#3c9160; }
.completion-item.summary_only { border-color:#dce7fa; background:#f5f8fe; }.completion-item.summary_only strong { color:#4879c7; }
.completion-item.missing { border-style:dashed; }.completion-item.missing strong { color:#b17b32; }
.independent-note { margin:12px 0 0; color:#79a387; font-size:10px; }
.review-matrix-card { margin-bottom:20px; padding:22px; overflow:hidden; }
.matrix-heading { align-items:center; }
.matrix-legend { display:flex; align-items:center; flex-wrap:wrap; gap:14px; color:#7d899b; font-size:10px; }
.matrix-legend span { display:flex; align-items:center; gap:6px; }
.matrix-legend i { width:7px; height:7px; border-radius:50%; background:#d5dce7; }
.matrix-legend i.ready { background:#42ad83; box-shadow:0 0 0 3px rgba(66,173,131,.12); }
.review-matrix-scroll { width:100%; overflow:auto; border:1px solid #d9e2ee; border-radius:11px; background:#fff; box-shadow:0 8px 24px rgba(33,67,112,.05); }
.review-matrix { width:100%; border-spacing:0; border-collapse:separate; table-layout:fixed; color:#435066; font-size:11px; }
.matrix-category-col { width:100px; }
.matrix-detail-col { width:180px; }
.matrix-month-col { width:112px; }
.matrix-change-col { width:140px; }
.matrix-ratio-col { width:150px; }
.matrix-reason-col { width:340px; }
.review-matrix th,.review-matrix td { height:46px; padding:8px 10px; border-right:1px solid #dfe6ef; border-bottom:1px solid #dfe6ef; vertical-align:middle; }
.review-matrix tr:last-child>th,.review-matrix tr:last-child>td { border-bottom:0; }
.review-matrix tr>th:last-child,.review-matrix tr>td:last-child { border-right:0; }
.review-matrix thead th { position:sticky; top:0; z-index:4; height:54px; color:#263b5c; background:linear-gradient(180deg,#f7faff 0%,#edf3fb 100%); font-size:11px; font-weight:700; text-align:center; line-height:1.45; }
.review-matrix thead th.is-current { color:#6f5813; background:linear-gradient(180deg,#fff9e8 0%,#fff2c6 100%); }
.review-matrix .matrix-summary-head { background:linear-gradient(180deg,#f3f8ff 0%,#e8f1ff 100%); }
.review-matrix .matrix-sticky { position:sticky; z-index:3; }
.review-matrix .matrix-category-head { left:0; z-index:6; }
.review-matrix .matrix-detail-head { left:100px; z-index:6; }
.matrix-category-cell { left:0; color:#1f3150; background:#f4f7fb; font-size:12px; font-weight:700; text-align:center; }
.matrix-detail-cell { left:100px; background:#fff; font-weight:600; text-align:left; }
.matrix-detail-cell>span,.matrix-detail-link { display:block; overflow:hidden; color:#34445e; font:inherit; text-overflow:ellipsis; white-space:nowrap; }
.matrix-detail-link { padding:0; border:0; color:#2f6feb; background:transparent; cursor:pointer; text-align:left; }
.matrix-detail-link:hover { text-decoration:underline; }
.matrix-detail-cell small { display:flex; margin-top:4px; align-items:center; gap:5px; color:#a0a9b7; font-size:9px; font-weight:400; }
.matrix-detail-cell small::before { width:5px; height:5px; border-radius:50%; background:#d4dae4; content:""; }
.matrix-detail-cell small.ready { color:#438970; }
.matrix-detail-cell small.ready::before { background:#4ab58c; }
.matrix-number-cell { color:#46546a; text-align:right; font-variant-numeric:tabular-nums; }
.matrix-number-cell.is-current { color:#5f4d18; background:#fff9e7; font-weight:700; }
.matrix-change-cell,.matrix-ratio-cell { color:#304766; background:#f8fbff; font-weight:700; }
.matrix-reason-cell { color:#59677a; background:#fcfdff; line-height:1.55; }
.matrix-reason-cell .placeholder { color:#a3adbb; }
.matrix-number-cell :deep(.el-input-number) { width:100%; }
.matrix-number-cell :deep(.el-input__inner) { text-align:right; }
.matrix-reason-cell :deep(.el-textarea__inner) { min-height:32px !important; padding:7px 9px; font-size:11px; line-height:1.45; }
.review-matrix tbody tr:hover td { background-color:#f5f9ff; }
.review-matrix tbody tr:hover .matrix-detail-cell { background:#f5f9ff; }
.review-matrix tbody tr:hover .matrix-number-cell.is-current { background:#fff5d3; }
.analysis-grid { display:grid; margin-bottom:20px; gap:20px; grid-template-columns:minmax(500px,1.6fr) minmax(320px,.85fr); }
.trend-card,.review-card { padding:24px 26px; }.card-heading { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:18px; }.card-heading h3 { margin:0 0 6px; color:#1d2a43; font-size:16px; }.card-heading p,.card-heading>span { margin:0; color:#8b96a8; font-size:11px; }
.trend-chart { width:100%; height:290px; }.review-copy { min-height:174px; padding:18px; border:1px solid #e8ecf2; border-radius:9px; color:#667389; background:#fafbfd; font-size:12px; line-height:1.8; }
.review-summary { margin:0; white-space:pre-wrap; }.review-sections { margin:14px 0 0; }.review-sections dt { margin-top:12px; color:#35445d; font-weight:700; }.review-sections dd { margin:3px 0 0; white-space:pre-wrap; }
.review-editor { display:grid; gap:11px; }.review-editor label>span { display:block; margin-bottom:5px; color:#59677d; font-size:11px; font-weight:700; }
.event-list { margin-top:14px; }.event-list>div { padding:12px 0; border-top:1px solid #edf0f4; }.event-list strong { margin-left:8px; font-size:12px; }.event-list p { margin:6px 0 0; color:#8490a3; font-size:11px; }
.detail-card { padding:25px 27px; }
.detail-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:28px; }
.detail-heading-copy { min-width:0; flex:1; }
.detail-title-row { display:flex; min-height:34px; align-items:center; flex-wrap:wrap; gap:10px 16px; }
.detail-heading h3 { margin:0; color:#1d2a43; font-size:18px; }
.detail-heading p { margin:7px 0 0; color:#8490a3; font-size:12px; }
.shipping-headline-stat {
  display:inline-flex;
  padding:6px 11px;
  align-items:baseline;
  gap:6px;
  border:1px solid #cfe0fb;
  border-radius:9px;
  color:#63748c;
  background:linear-gradient(135deg,#f7faff 0%,#edf4ff 100%);
  box-shadow:0 4px 12px rgba(47,111,235,.07);
}
.shipping-headline-stat span { font-size:10px; }
.shipping-headline-stat strong { color:#245fbd; font-size:20px; line-height:1; }
.shipping-headline-stat small { color:#7f8da2; font-size:10px; }
.shipping-chart-button { min-width:112px; border:0; border-radius:9px; background:linear-gradient(135deg,#3479e7 0%,#235fc3 100%); box-shadow:0 7px 16px rgba(47,111,235,.2); }
.shipping-snapshot-tag { display:inline-flex; align-items:center; gap:5px; border-radius:999px; }
:global(.shipping-chart-drawer .el-drawer__header) { margin:0; padding:22px 26px 18px; border-bottom:1px solid #e5ebf3; }
:global(.shipping-chart-drawer .el-drawer__body) { padding:0; background:#f4f7fb; }
.shipping-chart-header { display:flex; width:100%; padding-right:12px; align-items:center; justify-content:space-between; gap:20px; }
.shipping-chart-header span { color:#3f7ee8; font-size:9px; font-weight:800; letter-spacing:.16em; }
.shipping-chart-header h2 { margin:4px 0 0; color:#1d2d48; font-size:20px; }
.shipping-chart-header p { margin:5px 0 0; color:#8692a4; font-size:11px; }
.shipping-chart-panel { min-height:calc(100vh - 92px); padding:22px 24px 30px; }
.shipping-chart-kpis { display:grid; margin-bottom:16px; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; }
.shipping-chart-kpis article { position:relative; min-width:0; min-height:104px; padding:17px 18px; overflow:hidden; border:1px solid #e1e8f2; border-radius:13px; background:#fff; box-shadow:0 7px 20px rgba(36,65,106,.055); }
.shipping-chart-kpis article::before { position:absolute; top:0; bottom:0; left:0; width:3px; content:""; background:#a9c6f7; }
.shipping-chart-kpis article.primary { color:#fff; border-color:transparent; background:linear-gradient(135deg,#397ce8 0%,#245dbd 100%); box-shadow:0 10px 24px rgba(47,111,235,.2); }
.shipping-chart-kpis article.primary::before { display:none; }
.shipping-chart-kpis span,.shipping-chart-kpis small { display:block; color:#8491a4; font-size:10px; }
.shipping-chart-kpis strong { display:block; margin:8px 0 5px; overflow:hidden; color:#1e304d; font-size:22px; text-overflow:ellipsis; white-space:nowrap; }
.shipping-chart-kpis strong.team-name { font-size:16px; }
.shipping-chart-kpis article.primary span,.shipping-chart-kpis article.primary small { color:rgba(255,255,255,.74); }
.shipping-chart-kpis article.primary strong { color:#fff; font-size:27px; }
.shipping-chart-grid { display:grid; grid-template-columns:minmax(520px,1.45fr) minmax(350px,1fr); gap:16px; }
.shipping-chart-card { min-width:0; padding:19px 20px; border:1px solid #e1e8f2; border-radius:14px; background:#fff; box-shadow:0 8px 24px rgba(36,65,106,.055); }
.shipping-chart-title { display:flex; min-height:40px; align-items:flex-start; justify-content:space-between; gap:16px; }
.shipping-chart-title strong,.shipping-chart-title span { display:block; }
.shipping-chart-title strong { color:#243753; font-size:14px; }
.shipping-chart-title span { margin-top:5px; color:#8a96a8; font-size:10px; }
.shipping-ranking-chart,.shipping-share-chart { width:100%; height:380px; }
.shipping-trend-detail-chart { width:100%; height:315px; }
.return-component-card { grid-column:1 / -1; }
.return-component-chart { width:100%; height:340px; }
.concentration-list { display:grid; margin-top:8px; gap:8px; }
.concentration-list>div { display:grid; min-height:31px; align-items:center; grid-template-columns:24px minmax(0,1fr) 82px; gap:9px; }
.concentration-list .rank { display:grid; width:21px; height:21px; place-items:center; border-radius:7px; color:#65748a; background:#edf2f8; font-size:9px; font-weight:700; }
.concentration-list>div:nth-child(-n+3) .rank { color:#fff; background:linear-gradient(135deg,#5b91ec,#3473d8); }
.team-copy { min-width:0; }
.team-copy strong { display:block; margin-bottom:5px; overflow:hidden; color:#46556c; font-size:10px; text-overflow:ellipsis; white-space:nowrap; }
.team-copy :deep(.el-progress-bar__outer) { background:#edf2f8; }
.team-copy :deep(.el-progress-bar__inner) { background:linear-gradient(90deg,#78a8f7,#3f7ee8); }
.team-number { text-align:right; }
.team-number strong,.team-number span { display:block; }
.team-number strong { color:#35465f; font-size:10px; }
.team-number span { margin-top:2px; color:#8e99aa; font-size:9px; }
.shipping-chart-insight { display:flex; margin-top:16px; padding:13px 16px; align-items:flex-start; gap:12px; border:1px solid #d8e5f8; border-radius:11px; color:#61738e; background:linear-gradient(90deg,#f7faff,#eef5ff); font-size:11px; line-height:1.7; }
.shipping-chart-insight strong { flex:none; color:#316bc5; }
.detail-actions { display:flex; flex-wrap:wrap; align-items:center; justify-content:flex-end; gap:9px; }
.native-file-input { display:none; }
.detail-hint { margin:18px 0 14px; }
.detail-hint :deep(.el-alert__content),.detail-hint :deep(.el-alert__title) { width:100%; }
.staffing-template-alert { margin:-4px 0 14px; border:1px solid #f2d39a; border-radius:10px; background:linear-gradient(90deg,#fffaf0,#fffdf8); }
.staffing-template-alert strong { color:#9a6818; font-size:12px; }
.staffing-template-alert p { margin:5px 0 0; color:#826f50; font-size:11px; line-height:1.65; }
.detail-context-row {
  display:flex;
  width:100%;
  min-height:30px;
  align-items:center;
  justify-content:space-between;
  flex-wrap:wrap;
  gap:10px 24px;
}
.detail-context-copy { min-width:280px; flex:1; color:#6e7b8e; line-height:1.6; }
.detail-context-source { display:flex; min-width:0; max-width:68%; align-items:center; justify-content:flex-end; gap:9px; }
.detail-context-source>span { flex:none; color:#5f6f86; font-size:11px; font-weight:700; white-space:nowrap; }
.detail-context-source .batch-tags { justify-content:flex-end; }
.detail-stats {
  display:grid;
  margin-bottom:14px;
  grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
  gap:12px;
}
.detail-stats>div {
  position:relative;
  min-width:0;
  min-height:76px;
  padding:15px 18px 14px 20px;
  overflow:hidden;
  border:1px solid #e0e8f4;
  border-radius:11px;
  background:linear-gradient(145deg,#fff 0%,#f7faff 100%);
  box-shadow:0 5px 16px rgba(46,78,123,.05);
}
.detail-stats>div::before { position:absolute; top:0; bottom:0; left:0; width:3px; content:""; background:#4d8df7; }
.detail-stats span { display:block; margin-bottom:7px; color:#7e8ba0; font-size:11px; }
.detail-stats strong { color:#203451; font-size:18px; font-weight:700; }
.staffing-kpis { display:grid; margin:14px 0; grid-template-columns:repeat(5,minmax(120px,1fr)); gap:11px; }
.staffing-kpis article { position:relative; min-width:0; padding:15px 17px; overflow:hidden; border:1px solid #e2e9f3; border-radius:12px; background:linear-gradient(145deg,#fff,#f8fbff); box-shadow:0 6px 18px rgba(45,72,111,.055); }
.staffing-kpis article::before { position:absolute; top:0; right:0; left:0; height:3px; background:#4d8df7; content:""; }
.staffing-kpis article.tone-cyan::before { background:#21a7b7; }
.staffing-kpis article.tone-violet::before { background:#7c67db; }
.staffing-kpis article.tone-amber::before,.staffing-kpis article.tone-warning::before { background:#e9a23b; }
.staffing-kpis article.tone-danger::before { background:#e55d62; }
.staffing-kpis span { display:block; margin-bottom:8px; color:#7c899d; font-size:10px; }
.staffing-kpis strong { color:#203451; font-size:21px; font-variant-numeric:tabular-nums; }
.staffing-kpis small { margin-left:5px; color:#93a0b2; font-size:10px; }
.batch-tags { display:flex; min-width:0; align-items:center; flex-wrap:wrap; gap:8px; }
.batch-tags :deep(.el-tag) { max-width:100%; height:auto; min-height:24px; padding-top:3px; padding-bottom:3px; white-space:normal; }
.detail-table { width:100%; }
.export-config { display:grid; gap:20px; }
.export-config-section { padding:16px 18px; border:1px solid #e3eaf4; border-radius:12px; background:#fafcff; }
.export-config-section>strong { display:block; margin-bottom:12px; color:#263b5b; font-size:13px; }
.export-config-section small { display:block; margin-top:10px; color:#8b97a9; line-height:1.6; }
.export-scope-group { display:grid; gap:10px; }
.export-column-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 14px; }
.shipping-table-toolbar {
  display:flex;
  margin:14px 0 12px;
  padding:12px 14px;
  align-items:center;
  justify-content:space-between;
  gap:16px;
  border:1px solid #e1e9f5;
  border-radius:11px;
  background:linear-gradient(90deg,#fbfdff 0%,#f5f9ff 100%);
}
.shipping-table-toolbar :deep(.el-input) { width:min(360px,100%); }
.shipping-table-toolbar :deep(.el-input__wrapper) { border-radius:10px; box-shadow:0 0 0 1px #d7e2f1 inset; }
.shipping-table-toolbar :deep(.el-input__wrapper.is-focus) { box-shadow:0 0 0 1px #4d8df7 inset,0 0 0 3px rgba(77,141,247,.1); }
.shipping-table-toolbar>span { color:#7f8ca0; font-size:11px; white-space:nowrap; }
.shipping-table-toolbar strong { color:#2f6feb; font-size:12px; }
.shipping-table-toolbar i { margin-left:10px; color:#9aa5b5; font-style:normal; }
.staffing-table-toolbar { display:flex; margin:14px 0 12px; padding:12px 14px; align-items:center; justify-content:space-between; gap:16px; border:1px solid #e1e9f5; border-radius:11px; background:linear-gradient(90deg,#fbfdff,#f6f9ff); }
.staffing-table-toolbar :deep(.el-input) { width:min(360px,100%); }
.staffing-table-toolbar :deep(.el-input__wrapper) { border-radius:10px; box-shadow:0 0 0 1px #d7e2f1 inset; }
.staffing-table-toolbar>span { color:#7f8ca0; font-size:11px; white-space:nowrap; }
.staffing-table-toolbar strong { color:#2f6feb; font-size:12px; }
.staffing-table-toolbar i { margin-left:10px; color:#9aa5b5; font-style:normal; }
.shipping-detail-table {
  overflow:hidden;
  border:1px solid #dce6f5;
  border-top:3px solid #4d8df7;
  border-radius:12px 12px 0 0;
  box-shadow:0 8px 24px rgba(35,76,135,.07);
}
.shipping-detail-table :deep(.shipping-table-header th.el-table__cell) {
  height:54px;
  color:#263f63;
  border-right-color:#d8e3f3;
  border-bottom:1px solid #b9cff0;
  background:linear-gradient(180deg,#f7faff 0%,#eaf2ff 100%) !important;
  font-size:13px;
  font-weight:700;
}
.shipping-detail-table :deep(.shipping-table-header .cell) {
  display:flex;
  align-items:center;
  justify-content:center;
  letter-spacing:.04em;
}
.shipping-detail-table :deep(.el-table__body td.el-table__cell) { transition:background-color .18s ease; }
.shipping-detail-table :deep(.el-table__body tr:hover>td.el-table__cell) { background:#f2f7ff !important; }
.staffing-detail-table { overflow:hidden; border:1px solid #dce6f5; border-top:3px solid #4d8df7; border-radius:12px 12px 0 0; box-shadow:0 8px 24px rgba(35,76,135,.06); }
.staffing-detail-table :deep(th.el-table__cell) { height:52px; color:#29415f; background:linear-gradient(180deg,#f7faff,#edf4ff) !important; font-weight:700; }
.staffing-detail-table :deep(.el-table__header th.el-table__cell>.cell) { display:flex; align-items:center; justify-content:center; text-align:center; }
.staffing-detail-table :deep(.el-table__header .caret-wrapper) { flex:none; }
.staffing-detail-table :deep(.el-table__body tr:hover>td.el-table__cell) { background:#f5f9ff !important; }
.staffing-column-header { display:inline-flex; align-items:center; justify-content:center; gap:5px; }
.staffing-column-header.editable { color:#2869c7; }
.staffing-column-header.editable :deep(svg) { width:13px; height:13px; }
.staffing-team-cell { display:flex; min-height:70px; align-items:center; justify-content:center; flex-direction:column; gap:11px; text-align:center; }
.staffing-team-cell>span { color:#344b68; font-weight:600; }
.staffing-team-cell>div { display:flex; gap:4px; }
.staffing-editable-cell { width:100%; min-width:0; }
.staffing-editable-cell>button { display:flex; width:100%; min-height:34px; padding:6px 8px; align-items:center; justify-content:flex-end; gap:7px; border:1px solid transparent; border-radius:8px; color:#46566c; background:transparent; cursor:pointer; font:inherit; transition:.18s ease; }
.staffing-editable-cell>button:hover { border-color:#a8c8f7; color:#2869c7; background:#eef5ff; box-shadow:0 3px 10px rgba(57,112,190,.1); }
.staffing-editable-cell>button:disabled { color:#9aa6b7; cursor:not-allowed; opacity:.6; }
.staffing-editable-cell>button :deep(svg) { width:13px; height:13px; }
.staffing-editable-cell :deep(.el-input-number) { width:100%; }
.staffing-editable-cell :deep(.el-input__wrapper) { border-radius:8px; box-shadow:0 0 0 1px #8bb7fb inset,0 0 0 3px rgba(77,141,247,.09); }
.staffing-editable-cell :deep(.el-input__inner) { text-align:right; font-variant-numeric:tabular-nums; }
.staffing-analysis-cell { padding:9px 2px; color:#3c4c63; text-align:left; white-space:normal; }
.staffing-analysis-readonly { overflow:hidden; border:1px solid #dce6f3; border-radius:10px; background:#fbfdff; }
.staffing-analysis-heading { display:flex; min-height:34px; padding:3px 9px 3px 12px; align-items:center; justify-content:space-between; border-bottom:1px solid #e4ebf5; background:linear-gradient(90deg,#f0f6ff,#f8fbff); }
.staffing-analysis-heading>span { color:#4d72aa; font-size:11px; font-weight:700; letter-spacing:.08em; }
.staffing-analysis-readonly article { display:grid; padding:9px 12px; grid-template-columns:22px minmax(0,1fr); gap:8px; border-top:1px dashed #e2e9f3; }
.staffing-analysis-readonly article:first-of-type { border-top:0; }
.staffing-analysis-readonly article>b { display:flex; width:20px; height:20px; align-items:center; justify-content:center; border-radius:6px; color:#fff; background:#4d8df7; font-size:10px; }
.staffing-analysis-readonly article strong { display:block; margin-bottom:3px; color:#344b6b; font-size:11px; }
.staffing-analysis-readonly article p { margin:0; color:#5f6f84; font-size:12px; line-height:1.7; overflow-wrap:anywhere; white-space:pre-wrap; }
.staffing-analysis-readonly article.empty>b { background:#b5c0cf; }
.staffing-analysis-readonly article.empty p { color:#a0aaba; }
.staffing-analysis-editor { display:grid; padding:12px; gap:11px; border:1px solid #8bb7fb; border-radius:10px; background:#f8fbff; box-shadow:0 0 0 3px rgba(77,141,247,.08); }
.staffing-analysis-editor label { display:grid; grid-template-columns:128px minmax(0,1fr); align-items:start; gap:10px; }
.staffing-analysis-editor label>span { display:flex; padding-top:8px; align-items:center; gap:7px; color:#405875; font-size:11px; font-weight:700; }
.staffing-analysis-editor label>span b { display:inline-flex; width:20px; height:20px; align-items:center; justify-content:center; border-radius:6px; color:#fff; background:#4d8df7; font-size:10px; }
.staffing-analysis-editor :deep(.el-textarea__inner) { padding:8px 10px; border-radius:8px; color:#415169; line-height:1.65; resize:none; box-shadow:0 0 0 1px #d5dfec inset; }
.staffing-analysis-editor :deep(.el-textarea__inner:focus) { box-shadow:0 0 0 1px #4d8df7 inset,0 0 0 3px rgba(77,141,247,.09); }
.staffing-analysis-actions { display:flex; justify-content:flex-end; gap:6px; }
.staffing-delta { font-weight:700; font-variant-numeric:tabular-nums; }
.staffing-delta.positive { color:#219166; }
.staffing-delta.negative { color:#d75259; }
.shipping-consumption-amount { color:#8a96a8; font-variant-numeric:tabular-nums; }
.detail-pagination {
  display:flex;
  min-height:50px;
  margin-top:18px;
  padding:16px 4px 0;
  justify-content:flex-end;
  border-top:1px solid #e8edf5;
}
.preview-panel { min-height:240px; }
.system-preview { display:grid; gap:16px; }
.system-source-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }
.system-source-grid>div { padding:12px 14px; border:1px solid #e6ebf2; border-radius:8px; background:#fafbfd; }
.system-source-grid span { display:block; margin-bottom:5px; color:#8a96a8; font-size:10px; }
.system-source-grid strong { color:#263650; font-size:12px; }
.condition-list { display:flex; align-items:center; flex-wrap:wrap; gap:7px; color:#748197; font-size:11px; }
.replace-warning { margin-top:2px; }
.preview-meta { display:flex; flex-wrap:wrap; gap:18px; margin-bottom:15px; color:#6f7c90; font-size:12px; }
.preview-warning { margin-bottom:12px; }
.preview-summary { display:flex; margin-bottom:14px; align-items:center; flex-wrap:wrap; gap:8px; color:#647187; font-size:12px; }
.preview-note { margin:12px 0 0; color:#8b96a8; font-size:11px; }
.preview-footer { display:flex; align-items:center; justify-content:space-between; gap:20px; }
.preview-footer>div { display:flex; align-items:center; gap:10px; }
@media (max-width:1250px) { .completion-items { grid-template-columns:repeat(4,1fr); } }
@media (max-width:1250px) { .staffing-kpis { grid-template-columns:repeat(3,minmax(120px,1fr)); } }
@media (max-width:1150px) { .analysis-grid,.shipping-chart-grid { grid-template-columns:1fr; }.shipping-chart-kpis { grid-template-columns:repeat(3,minmax(0,1fr)); } }
@media (max-width:720px) { .shipping-table-toolbar,.staffing-table-toolbar { align-items:stretch; flex-direction:column; }.shipping-table-toolbar>span,.staffing-table-toolbar>span { white-space:normal; }.shipping-table-toolbar i,.staffing-table-toolbar i { display:block; margin:4px 0 0; }.staffing-kpis { grid-template-columns:repeat(2,minmax(110px,1fr)); }.detail-context-copy { min-width:100%; }.detail-context-source { width:100%; max-width:none; align-items:flex-start; flex-direction:column; }.detail-context-source .batch-tags { justify-content:flex-start; }.detail-pagination { overflow-x:auto; justify-content:flex-start; } }
@media (max-width:720px) { .heading-actions,.detail-heading,.preview-footer,.status-main,.completion-row,.matrix-heading,.shipping-chart-header { align-items:stretch; flex-direction:column; }.heading-actions,.detail-actions { flex-wrap:wrap; justify-content:flex-start; }.status-update { text-align:left; }.completion-row :deep(.el-progress) { width:100%; }.completion-items,.system-source-grid,.shipping-chart-kpis { grid-template-columns:repeat(2,1fr); }.review-matrix-card { padding:16px; }.shipping-chart-panel { padding:16px; }.shipping-ranking-chart,.shipping-share-chart { height:330px; }.shipping-chart-insight { flex-direction:column; } }
</style>
