<script setup lang="ts">
import {
  Check,
  CircleCheck,
  Download,
  EditPen,
  Lock,
  Refresh,
  TrendCharts,
  Unlock,
  UploadFilled,
} from '@element-plus/icons-vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import VChart from 'vue-echarts'
import {
  getAnalytics,
  getAnalyticsDetails,
  getAnalyticsDetailTypes,
  importAnalyticsDetails,
  previewAnalyticsImport,
  saveAnalytics,
  updateAnalyticsStatus,
  type AnalyticsData,
  type AnalyticsDetails,
  type AnalyticsDetailType,
  type AnalyticsImportPreview,
  type AnalyticsMetric,
} from '../api/analytics'
import { formatCount } from '../utils/format'
import { useAuthStore } from '../stores/auth'

use([CanvasRenderer, LineChart, GridComponent, LegendComponent, TooltipComponent])

const auth = useAuthStore()
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

const categoryOrder = ['发货', '退货', '客户', '供应商', '人员场地', '其他']
const groupedMetrics = computed(() => categoryOrder
  .map((category) => ({ category, metrics: data.value?.metrics.filter((metric) => metric.category === category) ?? [] }))
  .filter((group) => group.metrics.length))
const currentDetailType = computed(() => detailTypes.value.find((item) => item.code === activeTab.value))
const templateUrl = computed(() => `/api/v1/analytics/details/${activeTab.value}/template`)
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
  loading.value = true
  try {
    data.value = await getAnalytics(selectedMonth.value)
    resetEditor()
    editing.value = false
  } finally {
    loading.value = false
  }
}

async function loadDetails() {
  if (activeTab.value === 'summary') return
  detailLoading.value = true
  try {
    details.value = await getAnalyticsDetails(
      activeTab.value,
      selectedMonth.value,
      detailPage.value,
      detailPageSize.value,
    )
  } finally {
    detailLoading.value = false
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

function metricName(code: string) {
  return data.value?.metrics.find((metric) => metric.code === code)?.name || code
}

function formatImportedAt(value: string) {
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatActivity(value?: string | null) {
  return value ? formatImportedAt(value) : '暂无更新记录'
}

function sourceType(metric?: AnalyticsMetric) {
  if (!metric) return 'info'
  if (metric.source_type === 'excel') return 'success'
  if (metric.source_type === 'manual') return 'warning'
  return 'info'
}

function openDataset(code: string) {
  activeTab.value = code
}

async function onDetailFile(file: { raw?: File }) {
  if (!file.raw || activeTab.value === 'summary') return
  previewFile.value = file.raw
  previewLoading.value = true
  try {
    importPreview.value = await previewAnalyticsImport(activeTab.value, file.raw)
    importMode.value = 'replace'
    previewVisible.value = true
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    previewLoading.value = false
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
    const summaryMessage = result.updated_metrics.length
      ? `，并更新 ${result.updated_metrics.map((item) => item.name).join('、')}`
      : ''
    ElMessage.success(`${result.message}${summaryMessage}`)
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
  await refreshActive()
})
watch(activeTab, async () => {
  detailPage.value = 1
  details.value = undefined
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
        <ElTag v-if="item.metric?.value != null" :type="sourceType(item.metric)" effect="plain" size="small" class="metric-source">
          {{ item.metric?.source_label }}
        </ElTag>
      </div>
    </article>
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
          <ElTableColumn label="数据来源" width="180">
            <template #default="{ row }">
              <div v-if="row.value !== null" class="source-cell">
                <ElTag :type="sourceType(row)" effect="plain" size="small">{{ row.source_label }}</ElTag>
                <span :title="row.source_name || ''">{{ row.source_name || row.updated_by_name || '—' }}</span>
              </div>
              <span v-else>—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="变化原因/说明" min-width="260">
            <template #default="{ row }"><ElInput v-if="editing" v-model="editNotes[row.id]" placeholder="可选" /><span v-else>{{ row.note || '—' }}</span></template>
          </ElTableColumn>
        </ElTable>
      </div>
    </section>
  </template>

  <section v-else v-loading="detailLoading" class="surface-card detail-card">
    <div class="detail-heading">
      <div>
        <h3>{{ currentDetailType?.name }}</h3>
        <p>{{ currentDetailType?.description }}</p>
      </div>
      <div class="detail-actions">
        <ElTag v-if="isArchived" type="info" effect="plain"><ElIcon><Lock /></ElIcon> 本月已归档</ElTag>
        <ElButton tag="a" :href="templateUrl" :icon="Download">下载模板</ElButton>
        <ElUpload
          v-if="canManage"
          :auto-upload="false"
          :show-file-list="false"
          accept=".xlsx"
          :on-change="onDetailFile"
        >
          <ElButton type="primary" :icon="UploadFilled" :loading="previewLoading">上传 Excel</ElButton>
        </ElUpload>
      </div>
    </div>

    <ElAlert
      class="detail-hint"
      type="info"
      :closable="false"
      show-icon
      :title="currentDetailType?.summary_hint || ''"
    />

    <div class="detail-stats">
      <div><span>当前月份</span><strong>{{ selectedMonth }}</strong></div>
      <div><span>有效明细</span><strong>{{ details?.total ?? 0 }} 行</strong></div>
      <div><span>导入批次</span><strong>{{ details?.batches.length ?? 0 }} 个</strong></div>
      <div v-for="(value, code) in details?.summary" :key="code">
        <span>自动汇总 · {{ metricName(code) }}</span><strong>{{ formatCount(value) }}</strong>
      </div>
    </div>

    <div v-if="details?.batches.length" class="batch-list">
      <span>当前数据来源</span>
      <ElTag v-for="batch in details.batches" :key="`${batch.original_name}-${batch.imported_at}`" effect="plain">
        {{ batch.original_name }} · {{ batch.row_count }} 行 · {{ batch.imported_by_name || '历史导入' }} · {{ formatImportedAt(batch.imported_at) }}
      </ElTag>
    </div>

    <ElTable v-if="details?.columns.length" :data="details.rows" border stripe class="detail-table" row-key="id">
      <ElTableColumn type="index" label="#" width="58" fixed="left" />
      <ElTableColumn
        v-for="column in details.columns"
        :key="column"
        :label="column"
        min-width="150"
        show-overflow-tooltip
      >
        <template #default="{ row }">{{ displayDetailValue(row.values[column]) }}</template>
      </ElTableColumn>
      <ElTableColumn label="来源文件" min-width="190" fixed="right" show-overflow-tooltip>
        <template #default="{ row }">{{ row.source_name }}</template>
      </ElTableColumn>
    </ElTable>
    <ElEmpty v-else description="该月份尚未上传分表数据，可下载模板后导入" />
    <ElPagination
      v-if="(details?.total ?? 0) > detailPageSize"
      class="detail-pagination"
      background
      layout="prev, pager, next, total"
      :current-page="detailPage"
      :page-size="detailPageSize"
      :total="details?.total ?? 0"
      @current-change="changeDetailPage"
    />
  </section>

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
      <ElTable :data="importPreview.rows" border stripe max-height="430">
        <ElTableColumn type="index" label="#" width="56" fixed="left" />
        <ElTableColumn
          v-for="column in importPreview.columns"
          :key="column"
          :label="column"
          min-width="150"
          show-overflow-tooltip
        >
          <template #default="{ row }">{{ displayDetailValue(row[column]) }}</template>
        </ElTableColumn>
      </ElTable>
      <p v-if="importPreview.row_count > importPreview.rows.length" class="preview-note">
        这里只展示前 {{ importPreview.rows.length }} 行，确认后会导入全部 {{ importPreview.row_count }} 行。
      </p>
    </div>
    <template #footer>
      <div class="preview-footer">
        <div>
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
.completion-item.uploaded { border-color:#cfead9; background:#f4fbf6; }.completion-item.uploaded strong { color:#3c9160; }
.completion-item.summary_only { border-color:#dce7fa; background:#f5f8fe; }.completion-item.summary_only strong { color:#4879c7; }
.completion-item.missing { border-style:dashed; }.completion-item.missing strong { color:#b17b32; }
.independent-note { margin:12px 0 0; color:#79a387; font-size:10px; }
.metric-grid { display:grid; margin-bottom:20px; gap:17px; grid-template-columns:repeat(4,minmax(180px,1fr)); }
.metric-card { display:flex; min-height:128px; padding:22px; align-items:center; gap:16px; }
.metric-icon { display:grid; width:43px; height:43px; flex:0 0 auto; place-items:center; border-radius:12px; }
.metric-icon svg { width:22px; }
.metric-icon.blue { color:#2f6feb; background:#eaf1ff; }.metric-icon.cyan { color:#1696ac; background:#e7f7f9; }.metric-icon.purple { color:#7356d8; background:#f0ecff; }.metric-icon.orange { color:#d7832c; background:#fff2e5; }
.metric-card span { color:#758197; font-size:12px; }.metric-value { margin-top:7px; color:#15233e; font-size:25px; font-weight:700; }.metric-value small { color:#929dad; font-size:11px; font-weight:400; }.metric-card p { margin:5px 0 0; color:#8290a4; font-size:10px; }.metric-source { margin-top:8px; }
.analysis-grid { display:grid; margin-bottom:20px; gap:20px; grid-template-columns:minmax(500px,1.6fr) minmax(320px,.85fr); }
.trend-card,.review-card,.metrics-card { padding:24px 26px; }.card-heading { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:18px; }.card-heading h3 { margin:0 0 6px; color:#1d2a43; font-size:16px; }.card-heading p,.card-heading>span { margin:0; color:#8b96a8; font-size:11px; }
.trend-chart { width:100%; height:290px; }.review-copy { min-height:174px; padding:18px; border:1px solid #e8ecf2; border-radius:9px; color:#667389; background:#fafbfd; font-size:12px; line-height:1.8; }
.review-summary { margin:0; white-space:pre-wrap; }.review-sections { margin:14px 0 0; }.review-sections dt { margin-top:12px; color:#35445d; font-weight:700; }.review-sections dd { margin:3px 0 0; white-space:pre-wrap; }
.review-editor { display:grid; gap:11px; }.review-editor label>span { display:block; margin-bottom:5px; color:#59677d; font-size:11px; font-weight:700; }
.event-list { margin-top:14px; }.event-list>div { padding:12px 0; border-top:1px solid #edf0f4; }.event-list strong { margin-left:8px; font-size:12px; }.event-list p { margin:6px 0 0; color:#8490a3; font-size:11px; }
.metric-group { display:grid; margin-top:15px; grid-template-columns:90px minmax(0,1fr); gap:12px; }.group-title { padding:14px; color:#2f6feb; border-radius:8px; background:#f1f6ff; font-size:13px; font-weight:700; text-align:center; align-self:stretch; }.metric-group :deep(.el-input-number) { width:135px; }
.source-cell { display:flex; min-width:0; align-items:center; gap:7px; }.source-cell span { overflow:hidden; color:#8793a5; font-size:10px; text-overflow:ellipsis; white-space:nowrap; }
.detail-card { padding:25px 27px; }
.detail-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; }
.detail-heading h3 { margin:0 0 7px; color:#1d2a43; font-size:18px; }
.detail-heading p { margin:0; color:#8490a3; font-size:12px; }
.detail-actions { display:flex; align-items:center; gap:9px; }
.detail-hint { margin:20px 0; }
.detail-stats { display:flex; flex-wrap:wrap; gap:12px; margin-bottom:17px; }
.detail-stats>div { min-width:145px; padding:13px 16px; border:1px solid #e7ebf1; border-radius:9px; background:#fafbfd; }
.detail-stats span { display:block; margin-bottom:5px; color:#8a96a8; font-size:10px; }
.detail-stats strong { color:#263650; font-size:15px; }
.batch-list { display:flex; margin-bottom:15px; align-items:center; flex-wrap:wrap; gap:8px; color:#7d899b; font-size:11px; }
.detail-table { width:100%; }
.detail-pagination { display:flex; margin-top:18px; justify-content:flex-end; }
.preview-panel { min-height:240px; }
.preview-meta { display:flex; flex-wrap:wrap; gap:18px; margin-bottom:15px; color:#6f7c90; font-size:12px; }
.preview-warning { margin-bottom:12px; }
.preview-summary { display:flex; margin-bottom:14px; align-items:center; flex-wrap:wrap; gap:8px; color:#647187; font-size:12px; }
.preview-note { margin:12px 0 0; color:#8b96a8; font-size:11px; }
.preview-footer { display:flex; align-items:center; justify-content:space-between; gap:20px; }
.preview-footer>div { display:flex; align-items:center; gap:10px; }
@media (max-width:1250px) { .completion-items { grid-template-columns:repeat(4,1fr); } }
@media (max-width:1150px) { .metric-grid { grid-template-columns:repeat(2,1fr); }.analysis-grid { grid-template-columns:1fr; } }
@media (max-width:720px) { .heading-actions,.detail-heading,.preview-footer,.status-main,.completion-row { align-items:stretch; flex-direction:column; }.heading-actions,.detail-actions { flex-wrap:wrap; }.status-update { text-align:left; }.completion-row :deep(.el-progress) { width:100%; }.completion-items { grid-template-columns:repeat(2,1fr); }.metric-grid { grid-template-columns:1fr; }.metric-group { grid-template-columns:1fr; }.group-title { text-align:left; } }
</style>
