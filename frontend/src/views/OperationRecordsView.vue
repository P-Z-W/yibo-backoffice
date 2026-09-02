<script setup lang="ts">
import {
  ArrowDown,
  Delete,
  Download,
  Edit,
  Plus,
  Refresh,
  Search,
  UploadFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  createOperationRecord,
  deleteOperationRecord,
  downloadOperationTemplate,
  exportOperationRecords,
  getCustomerSourcePreview,
  getOperationRecords,
  importOperationRecords,
  syncCustomerSource,
  updateOperationRecord,
  type OperationDataset,
  type OperationRecord,
  type CustomerSourcePreviewRow,
} from '../api/operationRecords'
import { useAuthStore } from '../stores/auth'

type FieldType = 'text' | 'textarea' | 'number' | 'select' | 'datetime'
interface FieldConfig {
  key: string
  label: string
  type?: FieldType
  required?: boolean
  options?: string[]
  default?: string | number
  minWidth?: number
  span?: number
}

const props = defineProps<{ dataset: OperationDataset }>()
const auth = useAuthStore()
const configs: Record<OperationDataset, {
  title: string
  description: string
  searchPlaceholder: string
  fields: FieldConfig[]
  filterLabel?: string
  filterOptions?: string[]
  summaryCards: Array<{ key: string; label: string; hint: string; tone: string }>
}> = {
  customer_changes: {
    title: '客户管理',
    description: '维护新进、流失和意向客户记录，经营分析按月份自动汇总。',
    searchPlaceholder: '搜索客户名称、来源渠道或备注',
    filterLabel: '变化类型',
    filterOptions: ['新进', '流失', '意向'],
    fields: [
      { key: 'change_type', label: '变化类型', type: 'select', options: ['新进', '流失', '意向'], required: true, default: '新进', minWidth: 110 },
      { key: 'occurred_at', label: '发生时间', type: 'datetime', required: true, minWidth: 180 },
      { key: 'customer_name', label: '客户名称', minWidth: 190 },
      { key: 'source_channel', label: '来源渠道', minWidth: 150 },
      { key: 'quantity', label: '数量', type: 'number', required: true, default: 1, minWidth: 100 },
      { key: 'note', label: '备注', type: 'textarea', span: 2, minWidth: 240 },
    ],
    summaryCards: [
      { key: 'total', label: '本月记录', hint: '明细条数', tone: 'blue' },
      { key: 'new', label: '新进客户', hint: '按数量汇总', tone: 'green' },
      { key: 'lost', label: '流失客户', hint: '按数量汇总', tone: 'red' },
      { key: 'prospective', label: '意向客户', hint: '按数量汇总', tone: 'purple' },
    ],
  },
  value_added: {
    title: '增值服务',
    description: '维护各团队的增值服务类型与数量，经营分析按月份自动展示明细。',
    searchPlaceholder: '搜索团队、服务编码、服务名称或服务分组',
    fields: [
      { key: 'team_id', label: '团队ID', minWidth: 130 },
      { key: 'team_name', label: '团队名称', required: true, minWidth: 180 },
      { key: 'service_code', label: '服务编码', minWidth: 140 },
      { key: 'service_name', label: '服务名称', required: true, minWidth: 180 },
      { key: 'service_group', label: '服务分组', minWidth: 150 },
      { key: 'quantity', label: '数量', type: 'number', required: true, default: 0, minWidth: 110 },
    ],
    summaryCards: [
      { key: 'total', label: '本月记录', hint: '增值服务明细数', tone: 'blue' },
      { key: 'quantity', label: '服务总量', hint: '按数量汇总', tone: 'purple' },
      { key: 'teams', label: '涉及团队', hint: '团队名称去重', tone: 'green' },
      { key: 'services', label: '服务类型', hint: '服务名称去重', tone: 'orange' },
    ],
  },
  service_issues: {
    title: '客户服务管理',
    description: '维护投诉问题、原因、责任与整改闭环，经营分析按月份展示。',
    searchPlaceholder: '搜索团队、投诉类别、问题或责任归属',
    filterLabel: '整改状态',
    filterOptions: ['待核实', '整改中', '已完成', '已关闭'],
    fields: [
      { key: 'team_name', label: '团队名', minWidth: 150 },
      { key: 'complaint_category', label: '投诉大类', minWidth: 150 },
      { key: 'issue_description', label: '问题详细描述', type: 'textarea', required: true, span: 2, minWidth: 260 },
      { key: 'verified_cause', label: '核实原因', type: 'textarea', span: 2, minWidth: 230 },
      { key: 'responsibility', label: '责任归属', minWidth: 150 },
      { key: 'corrective_action', label: '整改措施', type: 'textarea', span: 2, minWidth: 230 },
      { key: 'status', label: '状态', type: 'select', options: ['待核实', '整改中', '已完成', '已关闭'], default: '待核实', minWidth: 110 },
    ],
    summaryCards: [
      { key: 'total', label: '本月问题', hint: '服务记录数', tone: 'blue' },
      { key: 'open', label: '处理中', hint: '待核实与整改中', tone: 'orange' },
      { key: 'completed', label: '已闭环', hint: '已完成与已关闭', tone: 'green' },
    ],
  },
  short_video: {
    title: '短视频管理',
    description: '维护每月短视频数量、类型、负责人和运营备注。',
    searchPlaceholder: '搜索短视频类型、负责人或备注',
    fields: [
      { key: 'video_count', label: '短视频数量', type: 'number', required: true, default: 0, minWidth: 130 },
      { key: 'video_type', label: '短视频类型', minWidth: 190 },
      { key: 'owner', label: '负责人', minWidth: 150 },
      { key: 'note', label: '备注', type: 'textarea', span: 2, minWidth: 260 },
    ],
    summaryCards: [
      { key: 'total', label: '本月记录', hint: '运营明细数', tone: 'blue' },
      { key: 'video_count', label: '短视频总量', hint: '按数量汇总', tone: 'purple' },
      { key: 'owners', label: '参与负责人', hint: '负责人去重', tone: 'green' },
    ],
  },
}

const config = computed(() => configs[props.dataset])
const month = ref(new Date().toISOString().slice(0, 7))
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const exporting = ref(false)
const records = ref<OperationRecord[]>([])
const customerSourceRows = ref<CustomerSourcePreviewRow[]>([])
const customerSourceLoading = ref(false)
const customerSourceSyncing = ref(false)
const customerSourceLoaded = ref(false)
const customerSourceTotal = ref(0)
const customerSourceRegisteredTotal = ref(0)
const customerSourceArchivedTotal = ref(0)
const customerSourcePendingTotal = ref(0)
const customerSourcePage = ref(1)
const customerSourcePageSize = ref(50)
const customerViewMode = ref<'source' | 'records'>('source')
const summary = reactive<Record<string, number>>({})
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const keyword = ref('')
const filterValue = ref('')
const dialogVisible = ref(false)
const editId = ref<number>()
const form = reactive<Record<string, string | number>>({})
const importFileInput = ref<HTMLInputElement>()
const canManage = computed(() => auth.can('operations_data.manage'))
const isCustomerSourceView = computed(
  () => props.dataset === 'customer_changes' && customerViewMode.value === 'source',
)
const pagedCustomerSourceRows = computed(() => {
  const start = (customerSourcePage.value - 1) * customerSourcePageSize.value
  return customerSourceRows.value.slice(start, start + customerSourcePageSize.value)
})
const pageDescription = computed(() => isCustomerSourceView.value
  ? '进入页面时读取一次云端客户最新状态，后续可按需手动更新。'
  : config.value.description)
let searchTimer: number | undefined

function errorText(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    || '操作失败，请稍后重试'
}

function formatTime(value: string | number) {
  return String(value || '').replace('T', ' ').slice(0, 16) || '—'
}

function formatCentsAsYuan(value: number | null) {
  if (value === null) return '未设置'
  return `约 ¥${(value / 100).toFixed(2)}`
}

async function loadCustomerSourcePreview() {
  customerSourceLoading.value = true
  try {
    const result = await getCustomerSourcePreview()
    customerSourceRows.value = result.rows
    customerSourceTotal.value = result.total
    customerSourceRegisteredTotal.value = result.registered_total ?? 0
    customerSourceArchivedTotal.value = result.archived_total ?? 0
    customerSourcePendingTotal.value = result.pending_total ?? result.total
    customerSourcePage.value = 1
    customerSourceLoaded.value = true
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    customerSourceLoading.value = false
  }
}

async function registerCustomerSource() {
  if (!customerSourcePendingTotal.value) {
    ElMessage.info('当前没有待登记的云端客户')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将按云端完整创建时间登记 ${customerSourcePendingTotal.value} 家待处理客户，已归档月份将自动跳过。是否继续？`,
      '登记新进客户',
      { type: 'info', confirmButtonText: '开始登记' },
    )
    customerSourceSyncing.value = true
    const result = await syncCustomerSource()
    const monthHint = result.affected_months.length
      ? `，涉及 ${result.affected_months.join('、')}`
      : ''
    ElMessage.success(`已登记 ${result.created_count} 家，跳过已登记 ${result.skipped_existing} 家${monthHint}`)
    if (result.skipped_archived) {
      ElMessage.warning(`${result.skipped_archived} 家属于已归档月份，未写入历史数据`)
    }
    await loadCustomerSourcePreview()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error))
  } finally {
    customerSourceSyncing.value = false
  }
}

function changeCustomerSourcePageSize(value: number) {
  customerSourcePageSize.value = value
  customerSourcePage.value = 1
}

async function changeCustomerViewMode(value: string | number) {
  if (value === 'records') await loadRecords()
}

function resetForm(row?: OperationRecord) {
  Object.keys(form).forEach((key) => delete form[key])
  for (const field of config.value.fields) {
    form[field.key] = row?.[field.key] ?? field.default ?? ''
  }
  if (props.dataset === 'customer_changes') {
    const value = String(row?.occurred_at || '')
    form.occurred_at = value ? value.replace('T', ' ').slice(0, 19) : `${month.value}-01 00:00:00`
  }
}

async function loadRecords() {
  loading.value = true
  try {
    const data = await getOperationRecords(props.dataset, {
      month: month.value,
      keyword: keyword.value.trim() || undefined,
      filter_value: filterValue.value || undefined,
      page: page.value,
      size: pageSize.value,
    })
    records.value = data.records
    total.value = data.total
    Object.keys(summary).forEach((key) => delete summary[key])
    Object.assign(summary, data.summary)
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    loading.value = false
  }
}

function scheduleSearch() {
  if (searchTimer !== undefined) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(async () => {
    page.value = 1
    await loadRecords()
  }, 250)
}

function openCreate() {
  editId.value = undefined
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: OperationRecord) {
  editId.value = row.id
  resetForm(row)
  dialogVisible.value = true
}

async function submit() {
  const missing = config.value.fields.find((field) => {
    const value = form[field.key]
    return field.required && (value === '' || value === null || value === undefined)
  })
  if (missing) {
    ElMessage.warning(`请填写${missing.label}`)
    return
  }
  saving.value = true
  try {
    const payload = { month: month.value, ...form }
    if (editId.value) await updateOperationRecord(props.dataset, editId.value, payload)
    else await createOperationRecord(props.dataset, payload)
    dialogVisible.value = false
    ElMessage.success(editId.value ? '记录已更新' : '记录已新增')
    await loadRecords()
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    saving.value = false
  }
}

async function removeRecord(row: OperationRecord) {
  try {
    await ElMessageBox.confirm('确定删除这条记录吗？删除后经营分析会同步更新。', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
    })
    await deleteOperationRecord(props.dataset, row.id)
    ElMessage.success('记录已删除')
    await loadRecords()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error))
  }
}

function saveBlob(response: { data: Blob; headers: Record<string, unknown> }, fallback: string) {
  const disposition = String(response.headers['content-disposition'] || '')
  const match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const filename = match?.[1] ? decodeURIComponent(match[1]) : fallback
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

async function handleExcelCommand(command: string) {
  if (command === 'import') {
    importFileInput.value?.click()
    return
  }
  try {
    saveBlob(await downloadOperationTemplate(props.dataset), `${config.value.title}导入模板.xlsx`)
  } catch (error) {
    ElMessage.error(errorText(error))
  }
}

async function handleImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.xlsx')) {
    ElMessage.warning('请选择 .xlsx 格式的导入表')
    return
  }
  try {
    await ElMessageBox.confirm(
      `本次数据计入 ${month.value}；记录ID留空新增，填写已有ID更新。是否继续？`,
      `导入${config.value.title}`,
      { type: 'info', confirmButtonText: '开始导入' },
    )
    importing.value = true
    const result = await importOperationRecords(props.dataset, file, month.value)
    ElMessage.success(`导入完成：新增 ${result.created_count} 条，更新 ${result.updated_count} 条，跳过 ${result.skipped_count} 条`)
    await loadRecords()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error))
  } finally {
    importing.value = false
  }
}

async function exportCurrent() {
  exporting.value = true
  try {
    const response = await exportOperationRecords(props.dataset, {
      month: month.value,
      keyword: keyword.value.trim() || undefined,
      filter_value: filterValue.value || undefined,
    })
    saveBlob(response, `${month.value}_${config.value.title}.xlsx`)
    ElMessage.success('已导出当前筛选范围的数据')
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    exporting.value = false
  }
}

function tagType(field: string, value: string | number) {
  if (field === 'change_type') {
    if (value === '新进') return 'success'
    if (value === '流失') return 'danger'
    return 'primary'
  }
  if (field === 'status') {
    if (value === '已完成' || value === '已关闭') return 'success'
    if (value === '整改中') return 'warning'
    return 'info'
  }
  return 'primary'
}

async function changePage(value: number) {
  page.value = value
  await loadRecords()
}

async function changePageSize(value: number) {
  pageSize.value = value
  page.value = 1
  await loadRecords()
}

watch(month, async () => {
  if (isCustomerSourceView.value) return
  page.value = 1
  await loadRecords()
})
watch(filterValue, async () => {
  if (isCustomerSourceView.value) return
  page.value = 1
  await loadRecords()
})
watch(() => props.dataset, async () => {
  page.value = 1
  keyword.value = ''
  filterValue.value = ''
  dialogVisible.value = false
  customerViewMode.value = props.dataset === 'customer_changes' ? 'source' : 'records'
  if (props.dataset === 'customer_changes') await loadCustomerSourcePreview()
  else await loadRecords()
})
onMounted(async () => {
  if (props.dataset === 'customer_changes') await loadCustomerSourcePreview()
  else await loadRecords()
})
</script>

<template>
  <div class="page-heading operation-heading">
    <div><h1>{{ config.title }}</h1><p>{{ pageDescription }}</p></div>
    <div class="heading-actions">
      <ElTag v-if="isCustomerSourceView" type="primary" effect="plain" size="large">云端只读预览</ElTag>
      <template v-else>
        <div class="month-control"><span>数据月份</span><ElDatePicker v-model="month" type="month" value-format="YYYY-MM" format="YYYY年MM月" :clearable="false" /></div>
        <ElButton v-if="canManage" type="primary" :icon="Plus" @click="openCreate">新增记录</ElButton>
      </template>
    </div>
  </div>

  <section v-if="!isCustomerSourceView" class="summary-grid" :style="{ '--summary-columns': config.summaryCards.length }">
    <article v-for="card in config.summaryCards" :key="card.key" :class="['surface-card', 'summary-card', card.tone]">
      <span>{{ card.label }}</span><strong>{{ summary[card.key] ?? 0 }}</strong><small>{{ card.hint }}</small>
    </article>
  </section>

  <section class="surface-card records-card">
    <ElTabs
      v-if="props.dataset === 'customer_changes'"
      v-model="customerViewMode"
      class="customer-source-tabs"
      @tab-change="changeCustomerViewMode"
    >
      <ElTabPane label="云端客户源" name="source" />
      <ElTabPane label="月度客户变化" name="records" />
    </ElTabs>

    <template v-if="isCustomerSourceView">
      <div class="source-preview-toolbar">
        <div>
          <strong>云端客户保留结果</strong>
          <span>筛选：deleted = 0，cooperation_type = 20，且 stock_send_price 为空或小于 99900</span>
        </div>
        <div class="source-preview-actions">
          <span v-if="customerSourceLoaded">共 <strong>{{ customerSourceTotal }}</strong> 条，已登记 {{ customerSourceRegisteredTotal }}，待登记 {{ customerSourcePendingTotal }}<template v-if="customerSourceArchivedTotal">，归档跳过 {{ customerSourceArchivedTotal }}</template></span>
          <span v-else>尚未读取云端数据</span>
          <ElButton
            v-if="canManage && customerSourceLoaded"
            type="success"
            :loading="customerSourceSyncing"
            :disabled="customerSourcePendingTotal === 0"
            @click="registerCustomerSource"
          >登记新进客户</ElButton>
          <ElButton type="primary" :icon="Refresh" :loading="customerSourceLoading" @click="loadCustomerSourcePreview">读取最新状态</ElButton>
        </div>
      </div>
      <ElTable
        v-loading="customerSourceLoading"
        :data="pagedCustomerSourceRows"
        border
        stripe
        max-height="620"
        row-key="team_id"
        class="record-table customer-source-table"
      >
        <ElTableColumn type="index" label="序号" width="70" align="center" :index="(index: number) => (customerSourcePage - 1) * customerSourcePageSize + index + 1" />
        <ElTableColumn prop="team_id" label="团队ID" min-width="150" align="center">
          <template #default="{ row }"><strong>{{ row.team_id ?? '—' }}</strong></template>
        </ElTableColumn>
        <ElTableColumn prop="team_name" label="团队名称" min-width="250" show-overflow-tooltip>
          <template #default="{ row }"><strong class="team-name-cell">{{ row.team_name || '—' }}</strong></template>
        </ElTableColumn>
        <ElTableColumn prop="created_time" label="创建时间" min-width="190" align="center">
          <template #default="{ row }">{{ formatTime(row.created_time) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="cooperation_type" label="合作类型" min-width="170" align="center">
          <template #default="{ row }">
            <ElTag v-if="row.cooperation_type === 20" type="primary" effect="plain">云仓合作</ElTag>
            <ElTag v-else type="info" effect="plain">{{ row.cooperation_type === null ? '未设置' : `类型 ${row.cooperation_type}` }}</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="stock_send_price" label="库存发货单价（原始值）" min-width="210" align="center">
          <template #default="{ row }">
            <div :class="['stock-send-price-cell', { abnormal: row.stock_send_price === 99900 }]">
              <strong>{{ row.stock_send_price ?? '—' }}</strong>
              <small>{{ formatCentsAsYuan(row.stock_send_price) }}</small>
              <ElTag v-if="row.stock_send_price === 99900" type="danger" effect="plain" size="small">疑似异常</ElTag>
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="viewable" label="是否隐藏" min-width="120" align="center">
          <template #default="{ row }">
            <ElTag v-if="row.viewable === true" type="success" effect="plain">否</ElTag>
            <ElTag v-else-if="row.viewable === false" type="danger" effect="plain">是</ElTag>
            <ElTag v-else type="info" effect="plain">未设置</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="registered" label="登记状态" min-width="120" align="center">
          <template #default="{ row }">
            <ElTag v-if="row.registered" type="success" effect="light">已登记</ElTag>
            <ElTag v-else-if="row.archived" type="info" effect="light">月份已归档</ElTag>
            <ElTag v-else type="warning" effect="light">待登记</ElTag>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElEmpty
        v-if="!customerSourceRows.length && !customerSourceLoading"
        :description="customerSourceLoaded ? '未读取到符合条件的云端客户数据' : '尚未读取，请点击“读取最新状态”'"
      />
      <div v-if="customerSourceRows.length" class="source-table-footer">
        <div class="source-preview-note">登记时完整保留云端 created_time，月度统计按发生时间范围计算；同一团队 ID 不会重复登记。</div>
        <ElPagination
          v-model:current-page="customerSourcePage"
          :page-size="customerSourcePageSize"
          :page-sizes="[50, 100, 200]"
          :total="customerSourceTotal"
          background
          class="source-pagination"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="changeCustomerSourcePageSize"
        />
      </div>
    </template>

    <template v-else>
      <div class="table-toolbar">
        <ElInput v-model="keyword" :prefix-icon="Search" clearable :placeholder="config.searchPlaceholder" @input="scheduleSearch" />
        <ElSelect v-if="config.filterOptions" v-model="filterValue" :aria-label="config.filterLabel">
          <ElOption :label="`全部${config.filterLabel}`" value="" />
          <ElOption v-for="option in config.filterOptions" :key="option" :label="option" :value="option" />
        </ElSelect>
        <div class="record-total">共 <strong>{{ total }}</strong> 条记录</div>
        <div class="toolbar-actions">
          <ElDropdown v-if="canManage" trigger="click" @command="handleExcelCommand">
            <ElButton :loading="importing"><UploadFilled /> Excel 导入 <ElIcon class="el-icon--right"><ArrowDown /></ElIcon></ElButton>
            <template #dropdown><ElDropdownMenu>
              <ElDropdownItem command="import" :icon="UploadFilled">选择 Excel 导入</ElDropdownItem>
              <ElDropdownItem command="template" :icon="Download" divided>下载导入模板</ElDropdownItem>
            </ElDropdownMenu></template>
          </ElDropdown>
          <ElButton type="primary" plain :icon="Download" :loading="exporting" :disabled="total === 0" @click="exportCurrent">导出数据</ElButton>
        </div>
        <input ref="importFileInput" class="visually-hidden" type="file" accept=".xlsx" @change="handleImportFile" />
      </div>

      <ElTable v-loading="loading" :data="records" border stripe row-key="id" class="record-table">
        <ElTableColumn type="index" label="序号" width="70" :index="(index: number) => (page - 1) * pageSize + index + 1" />
        <ElTableColumn v-if="props.dataset === 'customer_changes'" prop="source_team_id" label="团队ID" min-width="130">
          <template #default="{ row }">{{ row.source_team_id || '手工记录' }}</template>
        </ElTableColumn>
        <ElTableColumn v-for="field in config.fields" :key="field.key" :prop="field.key" :label="field.label" :min-width="field.minWidth || 140" show-overflow-tooltip>
          <template #default="{ row }">
            <ElTag v-if="field.key === 'change_type' || field.key === 'status'" :type="tagType(field.key, row[field.key])" effect="light">{{ row[field.key] }}</ElTag>
            <span v-else-if="field.type === 'datetime'">{{ formatTime(row[field.key]) }}</span>
            <strong v-else-if="field.type === 'number'">{{ row[field.key] }}</strong>
            <span v-else>{{ row[field.key] || '—' }}</span>
          </template>
        </ElTableColumn>
        <ElTableColumn label="最后更新" width="155"><template #default="{ row }">{{ formatTime(row.updated_at) }}</template></ElTableColumn>
        <ElTableColumn v-if="canManage" label="操作" width="140" fixed="right" align="center"><template #default="{ row }">
          <ElTag v-if="row.source_locked" type="info" effect="plain">云端登记</ElTag>
          <template v-else>
            <ElButton text type="primary" :icon="Edit" @click="openEdit(row)">编辑</ElButton>
            <ElButton text type="danger" :icon="Delete" @click="removeRecord(row)">删除</ElButton>
          </template>
        </template></ElTableColumn>
      </ElTable>
      <ElEmpty v-if="!records.length && !loading" :description="`${month} 暂无${config.title}数据`" />
      <ElPagination v-if="total > 0" class="pagination" background layout="total, sizes, prev, pager, next, jumper" :current-page="page" :page-size="pageSize" :page-sizes="[50, 100, 200]" :total="total" @current-change="changePage" @size-change="changePageSize" />
    </template>
  </section>

  <ElDialog v-model="dialogVisible" :title="editId ? `编辑${config.title}记录` : `新增${config.title}记录`" width="760px" destroy-on-close>
    <ElAlert type="info" :closable="false" show-icon :title="`本次记录计入 ${month}`" />
    <ElForm label-position="top" class="record-form"><div class="form-grid">
      <ElFormItem v-for="field in config.fields" :key="field.key" :label="field.label" :required="field.required" :class="{ 'span-2': field.span === 2 }">
        <ElSelect v-if="field.type === 'select'" v-model="form[field.key]"><ElOption v-for="option in field.options" :key="option" :label="option" :value="option" /></ElSelect>
        <ElDatePicker v-else-if="field.type === 'datetime'" v-model="form[field.key]" type="datetime" value-format="YYYY-MM-DD HH:mm:ss" format="YYYY-MM-DD HH:mm:ss" :clearable="false" />
        <ElInputNumber v-else-if="field.type === 'number'" v-model="form[field.key]" :min="0" :precision="0" controls-position="right" />
        <ElInput v-else-if="field.type === 'textarea'" v-model="form[field.key]" type="textarea" :rows="3" maxlength="3000" show-word-limit />
        <ElInput v-else v-model="form[field.key]" maxlength="160" />
      </ElFormItem>
    </div></ElForm>
    <template #footer><ElButton @click="dialogVisible = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="submit">保存</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.operation-heading{align-items:flex-end}.heading-actions{display:flex;align-items:flex-end;gap:10px}.month-control span{display:block;margin-bottom:6px;color:#7b8799;font-size:10px}.summary-grid{display:grid;margin-bottom:18px;grid-template-columns:repeat(var(--summary-columns),minmax(0,1fr));gap:15px}.summary-card{min-height:108px;padding:19px 22px;border-top:3px solid #6f9be6}.summary-card span{color:#7e8b9f;font-size:11px}.summary-card strong{display:block;margin:7px 0 4px;color:#203450;font-size:26px}.summary-card small{color:#98a3b3;font-size:10px}.summary-card.green{border-top-color:#5bb985}.summary-card.red{border-top-color:#e18484}.summary-card.purple{border-top-color:#8c79df}.summary-card.orange{border-top-color:#e2a05b}.records-card{padding:20px}.customer-source-tabs{margin:-4px 0 14px}.source-preview-toolbar{display:flex;margin-bottom:15px;padding:14px 16px;align-items:center;justify-content:space-between;gap:18px;border:1px solid #dbe7f8;border-radius:10px;background:linear-gradient(90deg,#f7faff,#f1f6ff)}.source-preview-toolbar strong,.source-preview-toolbar span{display:block}.source-preview-toolbar>div>strong{color:#263b5a;font-size:14px}.source-preview-toolbar>div>span{margin-top:5px;color:#8090a7;font-size:10px}.source-preview-actions{display:flex;align-items:center;gap:14px}.source-preview-actions>span{margin:0!important;white-space:nowrap}.source-preview-actions>span strong{display:inline;color:#2f6feb}.customer-source-table :deep(.el-table__row td){height:49px}.team-name-cell{color:#263b5a}.stock-send-price-cell{display:flex;align-items:center;justify-content:center;gap:7px}.stock-send-price-cell small{color:#8b98aa}.stock-send-price-cell.abnormal strong,.stock-send-price-cell.abnormal small{color:#d84c4c}.source-table-footer{display:flex;margin-top:16px;padding-top:14px;align-items:center;justify-content:space-between;gap:18px;border-top:1px solid #e8edf4}.source-preview-note{flex:1;padding:11px 14px;color:#7e8da3;background:#f7f9fc;font-size:10px}.source-pagination{flex-shrink:0}.table-toolbar{display:flex;margin-bottom:15px;align-items:center;gap:10px}.table-toolbar :deep(.el-input){width:min(390px,100%)}.table-toolbar :deep(.el-select){width:145px}.record-total{margin-left:auto;color:#8490a2;font-size:11px;white-space:nowrap}.record-total strong{color:#2f6feb}.toolbar-actions{display:flex;align-items:center;gap:9px}.toolbar-actions :deep(.el-button svg){width:14px;margin-right:5px}.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}.record-table{width:100%;overflow:hidden;border-radius:10px 10px 0 0}.record-table :deep(th.el-table__cell){color:#304766;background:#f1f6ff!important}.pagination{display:flex;margin-top:18px;padding-top:16px;justify-content:flex-end;border-top:1px solid #e8edf4}.record-form{margin-top:16px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 18px}.span-2{grid-column:1/-1}.form-grid :deep(.el-select),.form-grid :deep(.el-input-number),.form-grid :deep(.el-date-editor){width:100%}@media(max-width:1000px){.summary-grid{grid-template-columns:repeat(2,1fr)}.table-toolbar,.source-preview-toolbar{align-items:stretch;flex-wrap:wrap}.source-preview-actions{width:100%;justify-content:space-between}.source-table-footer{align-items:stretch;flex-direction:column}.source-pagination{overflow-x:auto}.toolbar-actions{width:100%;justify-content:flex-end}}@media(max-width:720px){.operation-heading,.heading-actions{align-items:stretch;flex-direction:column}.summary-grid,.form-grid{grid-template-columns:1fr}.source-preview-actions{align-items:stretch;flex-direction:column}.span-2{grid-column:auto}.pagination{overflow-x:auto;justify-content:flex-start}}
</style>
