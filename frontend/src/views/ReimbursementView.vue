<script setup lang="ts">
import {
  Check,
  Close,
  CopyDocument,
  Delete,
  Download,
  Edit,
  Paperclip,
  Plus,
  Setting,
  UploadFilled,
  View,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  approveReimbursement,
  createReimbursement,
  deleteReimbursement,
  deleteReimbursementAttachment,
  exportReimbursements,
  getReimbursement,
  getReimbursements,
  importBatchReimbursements,
  markReimbursementsExported,
  previewBatchReimbursementImport,
  previewReimbursementImport,
  returnReimbursement,
  saveReimbursementConfig,
  submitReimbursement,
  updateReimbursement,
  uploadReimbursementAttachment,
  type ApprovalRecord,
  type BatchImportPreview,
  type ReimbursementAttachment,
  type ReimbursementItem,
  type ReimbursementPayload,
  type ReimbursementRecord,
} from '../api/reimbursement'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const records = ref<ReimbursementRecord[]>([])
const selectedRows = ref<ReimbursementRecord[]>([])
const summary = reactive({
  pending_supervisor: 0,
  pending_finance: 0,
  pending_export: 0,
  month_approved_count: 0,
  month_approved_amount: 0,
})
const config = reactive({
  finance_approval_enabled: false,
  teams: ['发货组', '退货组'],
  expense_categories: ['临时运费', '退件运费', '其他'],
})
const permissions = reactive({ can_configure: false, can_export: false })
const filters = reactive({ view: 'all', team: '', keyword: '', dateRange: [] as string[] })

const editorVisible = ref(false)
const editorSaving = ref(false)
const submitting = ref(false)
const editorId = ref<number>()
const autoSaveText = ref('')
const existingAttachments = ref<ReimbursementAttachment[]>([])
const uploadQueue = ref<File[]>([])
const uploading = ref(false)
const pasteVisible = ref(false)
const pasteText = ref('')
const form = reactive<ReimbursementPayload>({
  applicant_name: '',
  team: '发货组',
  note: '',
  items: [],
})

const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<ReimbursementRecord>()
const configVisible = ref(false)
const configSaving = ref(false)
const financeApprovalDraft = ref(false)
const batchVisible = ref(false)
const batchFile = ref<File>()
const batchFileName = ref('')
const batchPreview = ref<BatchImportPreview>()
const batchPreviewing = ref(false)
const batchImporting = ref(false)
const batchSubmit = ref(false)

let autoSaveTimer: number | undefined
let keywordTimer: number | undefined

const totalAmount = computed(() =>
  form.items.reduce((total, item) => total + Number(item.amount || 0), 0),
)
const hasSubstance = computed(
  () =>
    Boolean(form.note.trim()) ||
    form.items.some(
      (item) =>
        Number(item.amount) > 0 || Boolean(item.related_number.trim()) || Boolean(item.description.trim()),
    ),
)
const exportCandidates = computed(() => {
  return selectedRows.value.length ? selectedRows.value : records.value
})

function today() {
  return new Date().toISOString().slice(0, 10)
}

function newItem(source?: ReimbursementItem): ReimbursementItem {
  return {
    expense_date: source?.expense_date || today(),
    category: source?.category || config.expense_categories[0] || '其他',
    amount: source?.amount || 0,
    related_number: source?.related_number || '',
    description: source?.description || '',
  }
}

function formatMoney(value: number) {
  return Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function formatDateTime(value: string) {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 16)
}

function formatSize(value: number) {
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function errorText(error: unknown) {
  const response = (error as { response?: { data?: { detail?: string } } }).response
  return response?.data?.detail || '操作失败，请稍后重试'
}

function statusType(row: ReimbursementRecord) {
  if (row.status === 'returned') return 'danger'
  if (row.status === 'pending_supervisor' || row.status === 'pending_finance') return 'warning'
  if (row.status === 'approved' && !row.exported) return 'success'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const data = await getReimbursements({
      view: filters.view,
      team: filters.team,
      keyword: filters.keyword,
      start_date: filters.dateRange[0] || '',
      end_date: filters.dateRange[1] || '',
    })
    records.value = data.records
    Object.assign(summary, data.summary)
    Object.assign(config, data.config)
    Object.assign(permissions, data.permissions)
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    loading.value = false
  }
}

function resetForm() {
  editorId.value = undefined
  form.applicant_name = auth.user?.display_name || ''
  form.team = auth.user?.team || '发货组'
  form.note = ''
  form.items = [newItem()]
  existingAttachments.value = []
  uploadQueue.value = []
  autoSaveText.value = ''
}

function openNew() {
  resetForm()
  editorVisible.value = true
}

async function openEdit(row: ReimbursementRecord) {
  detailVisible.value = false
  editorSaving.value = true
  try {
    const data = await getReimbursement(row.id)
    editorId.value = data.id
    form.applicant_name = data.applicant_name
    form.team = data.team
    form.note = data.note
    form.items = (data.items || []).map((item) => newItem(item))
    existingAttachments.value = data.attachments || []
    autoSaveText.value = '草稿已保存'
    editorVisible.value = true
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    editorSaving.value = false
  }
}

function payload(): ReimbursementPayload {
  return {
    applicant_name: form.applicant_name.trim(),
    team: form.team,
    note: form.note.trim(),
    items: form.items.map((item) => ({
      expense_date: item.expense_date,
      category: item.category.trim(),
      amount: Number(item.amount || 0),
      related_number: item.related_number.trim(),
      description: item.description.trim(),
    })),
  }
}

async function saveDraft(silent = false) {
  if (!form.applicant_name.trim() || !form.team || !form.items.length) return undefined
  editorSaving.value = true
  autoSaveText.value = '正在保存…'
  try {
    const data = editorId.value
      ? await updateReimbursement(editorId.value, payload())
      : await createReimbursement(payload())
    editorId.value = data.id
    autoSaveText.value = `草稿已自动保存 ${new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
    if (!silent) ElMessage.success('草稿已保存')
    return data
  } catch (error) {
    autoSaveText.value = '自动保存失败'
    if (!silent) ElMessage.error(errorText(error))
    return undefined
  } finally {
    editorSaving.value = false
  }
}

function scheduleAutoSave() {
  if (!editorVisible.value || editorSaving.value || submitting.value || !hasSubstance.value) return
  window.clearTimeout(autoSaveTimer)
  autoSaveTimer = window.setTimeout(() => void saveDraft(true), 900)
}

function addRow(afterIndex?: number) {
  const source = typeof afterIndex === 'number' ? form.items[afterIndex] : form.items.at(-1)
  const item = newItem(source)
  item.amount = 0
  item.related_number = ''
  item.description = ''
  if (typeof afterIndex === 'number') form.items.splice(afterIndex + 1, 0, item)
  else form.items.push(item)
}

function copyRow(index: number) {
  form.items.splice(index + 1, 0, newItem(form.items[index]))
}

function removeRow(index: number) {
  if (form.items.length === 1) {
    form.items[0] = newItem()
    return
  }
  form.items.splice(index, 1)
}

async function submit() {
  const invalidIndex = form.items.findIndex(
    (item) => !item.expense_date || !item.category.trim() || Number(item.amount) <= 0,
  )
  if (!form.applicant_name.trim()) return ElMessage.warning('请输入报销人')
  if (invalidIndex >= 0) return ElMessage.warning(`请完善第 ${invalidIndex + 1} 条明细，金额必须大于 0`)
  submitting.value = true
  window.clearTimeout(autoSaveTimer)
  try {
    const saved = await saveDraft(true)
    if (!saved || !editorId.value) return
    await processUploadQueue()
    await submitReimbursement(editorId.value)
    editorVisible.value = false
    ElMessage.success('已提交主管审批')
    await load()
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    submitting.value = false
  }
}

async function removeDraft() {
  if (!editorId.value) {
    editorVisible.value = false
    return
  }
  try {
    await ElMessageBox.confirm('确定删除这张草稿吗？附件也会一并删除。', '删除草稿', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteReimbursement(editorId.value)
    editorVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(errorText(error))
  }
}

async function queueAttachment(file: File) {
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning(`${file.name} 超过 10MB，未加入上传`)
    return
  }
  uploadQueue.value.push(file)
  await processUploadQueue()
}

async function processUploadQueue() {
  if (uploading.value || !uploadQueue.value.length) return
  uploading.value = true
  try {
    if (!editorId.value) {
      const saved = await saveDraft(true)
      if (!saved) return
    }
    while (uploadQueue.value.length && editorId.value) {
      const file = uploadQueue.value[0]
      try {
        const result = await uploadReimbursementAttachment(editorId.value, file)
        existingAttachments.value.push(result)
        if (result.duplicate) ElMessage.warning(`${file.name} 与历史报销凭证重复，请核对`)
      } catch (error) {
        ElMessage.error(`${file.name}：${errorText(error)}`)
      } finally {
        uploadQueue.value.shift()
      }
    }
  } finally {
    uploading.value = false
  }
}

function onAttachmentChange(file: { raw?: File }) {
  if (file.raw) void queueAttachment(file.raw)
}

async function removeAttachment(item: ReimbursementAttachment) {
  if (!editorId.value) return
  try {
    await deleteReimbursementAttachment(editorId.value, item.id)
    existingAttachments.value = existingAttachments.value.filter((value) => value.id !== item.id)
  } catch (error) {
    ElMessage.error(errorText(error))
  }
}

function handlePaste(event: ClipboardEvent) {
  if (!editorVisible.value) return
  const files = Array.from(event.clipboardData?.files || []).filter((file) =>
    file.type.startsWith('image/'),
  )
  if (!files.length) return
  event.preventDefault()
  files.forEach((file, index) => {
    const named = new File([file], file.name || `粘贴凭证_${Date.now()}_${index + 1}.png`, {
      type: file.type,
    })
    void queueAttachment(named)
  })
  ElMessage.success(`已识别 ${files.length} 张粘贴图片`)
}

async function onImportChange(file: { raw?: File }) {
  if (!file.raw) return
  try {
    const result = await previewReimbursementImport(file.raw)
    if (result.items.length) form.items = result.items.map((item) => newItem(item))
    if (result.errors.length) {
      ElMessage.warning(`已导入 ${result.count} 条，另有 ${result.errors.length} 行需要修正`)
    } else {
      ElMessage.success(`已导入 ${result.count} 条费用明细`)
    }
  } catch (error) {
    ElMessage.error(errorText(error))
  }
}

function applyPaste() {
  const lines = pasteText.value.trim().split(/\r?\n/).filter(Boolean)
  const items: ReimbursementItem[] = []
  for (const [index, line] of lines.entries()) {
    const cells = line.split('\t').map((value) => value.trim())
    if (index === 0 && cells.some((value) => value.includes('费用') || value === '日期')) continue
    const hasDate = /^\d{4}[-/]\d{1,2}[-/]\d{1,2}$/.test(cells[0] || '')
    const normalizedDate = hasDate ? cells[0].replaceAll('/', '-') : today()
    const offset = hasDate ? 0 : -1
    const category = cells[1 + offset] || config.expense_categories[0] || '其他'
    const amount = Number(String(cells[2 + offset] || '').replace(/[¥,，\s]/g, ''))
    if (!Number.isFinite(amount) || amount <= 0) continue
    items.push({
      expense_date: normalizedDate,
      category,
      amount,
      related_number: cells[3 + offset] || '',
      description: cells[4 + offset] || '',
    })
  }
  if (!items.length) return ElMessage.warning('没有识别到有效数据，请从 Excel 复制后再粘贴')
  form.items = items
  pasteVisible.value = false
  pasteText.value = ''
  ElMessage.success(`已粘贴 ${items.length} 条明细`)
}

async function openDetail(row: ReimbursementRecord) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    detail.value = await getReimbursement(row.id)
  } catch (error) {
    ElMessage.error(errorText(error))
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

async function approveCurrent() {
  if (!detail.value) return
  try {
    const result = await ElMessageBox.prompt('可以填写审批意见，也可以直接通过。', '审批通过', {
      confirmButtonText: '确认通过',
      cancelButtonText: '取消',
      inputPlaceholder: '审批意见（选填）',
    })
    detail.value = await approveReimbursement(detail.value.id, result.value)
    ElMessage.success(detail.value.status === 'pending_finance' ? '已交财务审批' : '审批已完成，可导出')
    await load()
  } catch (error) {
    const message = errorText(error)
    if (message !== '操作失败，请稍后重试') ElMessage.error(message)
  }
}

async function returnCurrent() {
  if (!detail.value) return
  try {
    const result = await ElMessageBox.prompt('请说明需要修改的内容，报销人修改后可重新提交。', '退回修改', {
      confirmButtonText: '确认退回',
      cancelButtonText: '取消',
      inputPlaceholder: '退回原因（必填）',
      inputValidator: (value) => Boolean(value.trim()) || '请输入退回原因',
    })
    detail.value = await returnReimbursement(detail.value.id, result.value)
    ElMessage.success('已退回报销人修改')
    await load()
  } catch (error) {
    const message = errorText(error)
    if (message !== '操作失败，请稍后重试') ElMessage.error(message)
  }
}

async function exportSelected() {
  const candidates = exportCandidates.value
  if (!candidates.length) return ElMessage.warning('当前列表没有可导出的报销单')
  const total = candidates.reduce((sum, row) => sum + row.total_amount, 0)
  try {
    await ElMessageBox.confirm(
      `将导出 ${candidates.length} 张报销单，合计 ¥${formatMoney(total)}。导出只记录批次，不改变审批状态，并且可以重复导出。`,
      '导出报销数据',
      { confirmButtonText: '导出 Excel', cancelButtonText: '取消', type: 'info' },
    )
    const ids = candidates.map((row) => row.id)
    await exportReimbursements(ids)
    const result = await markReimbursementsExported(ids)
    ElMessage.success(`导出完成，批次 ${result.batch}`)
    await load()
  } catch (error) {
    const message = errorText(error)
    if (message !== '操作失败，请稍后重试') ElMessage.error(message)
  }
}

function openBatchImport() {
  batchFile.value = undefined
  batchFileName.value = ''
  batchPreview.value = undefined
  batchSubmit.value = false
  batchVisible.value = true
}

async function onBatchFileChange(file: { raw?: File; name?: string }) {
  if (!file.raw) return
  batchFile.value = file.raw
  batchFileName.value = file.name || file.raw.name
  batchPreview.value = undefined
  batchPreviewing.value = true
  try {
    batchPreview.value = await previewBatchReimbursementImport(file.raw)
    if (batchPreview.value.can_import) {
      ElMessage.success(
        `校验通过：将生成 ${batchPreview.value.claim_count} 张报销单、${batchPreview.value.item_count} 条明细`,
      )
    }
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    batchPreviewing.value = false
  }
}

async function confirmBatchImport() {
  if (!batchFile.value || !batchPreview.value?.can_import) return
  batchImporting.value = true
  try {
    const result = await importBatchReimbursements(batchFile.value, batchSubmit.value)
    batchVisible.value = false
    filters.view = batchSubmit.value ? 'mine' : 'all'
    await load()
    ElMessage.success(
      `已批量生成 ${result.claim_count} 张报销单，共 ${result.item_count} 条明细，合计 ¥${formatMoney(result.total_amount)}`,
    )
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    batchImporting.value = false
  }
}

function openConfig() {
  financeApprovalDraft.value = config.finance_approval_enabled
  configVisible.value = true
}

async function saveConfig() {
  configSaving.value = true
  try {
    await saveReimbursementConfig(financeApprovalDraft.value)
    config.finance_approval_enabled = financeApprovalDraft.value
    configVisible.value = false
    ElMessage.success('流程设置已保存，新提交的报销单将按新流程执行')
    await load()
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    configSaving.value = false
  }
}

function approvalTitle(record: ApprovalRecord) {
  const labels: Record<string, string> = {
    create: '创建草稿',
    submit: '提交主管审批',
    supervisor_approve: '主管审批通过',
    finance_approve: '财务审批通过',
    return: '退回修改',
    export: '导出给财务',
  }
  return labels[record.action] || record.action
}

watch(form, scheduleAutoSave, { deep: true })
watch(() => [filters.view, filters.team, filters.dateRange], () => void load(), { deep: true })
watch(
  () => filters.keyword,
  () => {
    window.clearTimeout(keywordTimer)
    keywordTimer = window.setTimeout(() => void load(), 350)
  },
)

onMounted(() => {
  document.addEventListener('paste', handlePaste)
  void load()
})
onBeforeUnmount(() => {
  document.removeEventListener('paste', handlePaste)
  window.clearTimeout(autoSaveTimer)
  window.clearTimeout(keywordTimer)
})
</script>

<template>
  <div class="page-heading">
    <div><h1>报销管理</h1><p>员工快速录入，主管审批后统一导出给财务。</p></div>
    <div class="page-actions">
      <ElButton v-if="permissions.can_configure" :icon="Setting" @click="openConfig">流程设置</ElButton>
      <ElButton v-if="permissions.can_export" :icon="Download" @click="exportSelected">导出数据</ElButton>
      <ElButton v-if="auth.can('reimbursement.create')" :icon="UploadFilled" @click="openBatchImport">Excel 批量导入</ElButton>
      <ElButton v-if="auth.can('reimbursement.create')" type="primary" :icon="Plus" @click="openNew">新建报销</ElButton>
    </div>
  </div>

  <section class="summary-grid">
    <article class="surface-card"><div class="summary-icon amber"><Check /></div><div><span>待主管审批</span><strong>{{ summary.pending_supervisor }}</strong><small>等待仓库主管处理</small></div></article>
    <article class="surface-card"><div class="summary-icon purple"><View /></div><div><span>待财务审批</span><strong>{{ summary.pending_finance }}</strong><small>{{ config.finance_approval_enabled ? '财务审批已启用' : '当前流程未启用' }}</small></div></article>
    <article class="surface-card"><div class="summary-icon green"><Download /></div><div><span>未导出</span><strong>{{ summary.pending_export }}</strong><small>任意状态均可勾选导出</small></div></article>
    <article class="surface-card"><div class="summary-icon blue"><CopyDocument /></div><div><span>本月审批金额</span><strong class="money">¥ {{ formatMoney(summary.month_approved_amount) }}</strong><small>共 {{ summary.month_approved_count }} 张报销单</small></div></article>
  </section>

  <section class="surface-card table-card">
    <div class="toolbar">
      <ElSegmented v-model="filters.view" :options="[
        { label: '全部', value: 'all' },
        { label: '待我审批', value: 'mine' },
        { label: '未导出', value: 'pending_export' },
        { label: '已导出', value: 'exported' },
      ]" />
      <div class="filters">
        <ElInput v-model="filters.keyword" placeholder="搜索单号、报销人或关联单号" clearable />
        <ElSelect v-model="filters.team" placeholder="全部组别" clearable><ElOption v-for="team in config.teams" :key="team" :label="team" :value="team" /></ElSelect>
        <ElDatePicker v-model="filters.dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" />
      </div>
    </div>

    <ElTable v-loading="loading" :data="records" stripe @selection-change="selectedRows = $event">
      <ElTableColumn type="selection" width="48" />
      <ElTableColumn prop="number" label="报销单号" min-width="160" />
      <ElTableColumn prop="applicant_name" label="报销人" width="110" />
      <ElTableColumn prop="team" label="所属组" width="100" />
      <ElTableColumn prop="item_summary" label="费用摘要" min-width="220" show-overflow-tooltip />
      <ElTableColumn label="报销金额" width="135"><template #default="{ row }"><strong class="table-money">¥ {{ formatMoney(row.total_amount) }}</strong></template></ElTableColumn>
      <ElTableColumn label="提交时间" width="155"><template #default="{ row }">{{ formatDateTime(row.submitted_at || row.created_at) }}</template></ElTableColumn>
      <ElTableColumn label="状态" width="130"><template #default="{ row }"><ElTag :type="statusType(row)" effect="light" round>{{ row.status_label }}</ElTag></template></ElTableColumn>
      <ElTableColumn label="导出记录" width="115"><template #default="{ row }"><ElTag :type="row.exported ? 'success' : 'info'" effect="plain" :title="row.export_batch || '尚未导出'">{{ row.exported ? '已导出' : '未导出' }}</ElTag></template></ElTableColumn>
      <ElTableColumn label="操作" width="160" fixed="right"><template #default="{ row }"><ElButton text type="primary" :icon="View" @click="openDetail(row)">查看</ElButton><ElButton v-if="row.can_edit" text type="primary" :icon="Edit" @click="openEdit(row)">编辑</ElButton></template></ElTableColumn>
      <template #empty><ElEmpty description="暂无符合条件的报销单"><ElButton v-if="auth.can('reimbursement.create')" type="primary" plain @click="openNew">新建第一张报销单</ElButton></ElEmpty></template>
    </ElTable>
  </section>

  <ElDrawer v-model="editorVisible" size="min(1180px, 94vw)" :close-on-click-modal="false" class="reimbursement-drawer" @closed="load">
    <template #header><div class="drawer-title"><div><h2>{{ editorId ? '编辑报销单' : '新建报销' }}</h2><p>{{ editorId ? `可随时关闭，数据不会丢失` : '填写任意金额后自动保存草稿' }}</p></div><ElTag v-if="autoSaveText" type="info" effect="plain">{{ autoSaveText }}</ElTag></div></template>
    <div class="editor-content">
      <section class="editor-section basic-section">
        <div class="section-heading"><div><h3>基本信息</h3><p>报销人和所属组会自动带出，也可以直接修改。</p></div></div>
        <div class="basic-grid">
          <ElFormItem label="报销人"><ElInput v-model="form.applicant_name" placeholder="请输入姓名" /></ElFormItem>
          <ElFormItem label="所属组"><ElSelect v-model="form.team"><ElOption v-for="team in config.teams" :key="team" :label="team" :value="team" /></ElSelect></ElFormItem>
          <ElFormItem label="整单说明"><ElInput v-model="form.note" placeholder="选填，例如本周退件运费汇总" /></ElFormItem>
        </div>
      </section>

      <section class="editor-section detail-section">
        <div class="section-heading quick-heading">
          <div><h3>费用明细</h3><p>支持逐行填写、从 Excel 直接粘贴或上传模板。</p></div>
          <div class="quick-actions">
            <ElButton :icon="CopyDocument" @click="pasteVisible = true">粘贴多行</ElButton>
            <ElUpload :auto-upload="false" :show-file-list="false" accept=".xlsx" :on-change="onImportChange"><ElButton :icon="UploadFilled">导入 Excel</ElButton></ElUpload>
            <ElButton tag="a" href="/api/v1/reimbursements/template/xlsx" :icon="Download">下载模板</ElButton>
          </div>
        </div>
        <ElTable :data="form.items" class="entry-table" border>
          <ElTableColumn label="#" width="48"><template #default="{ $index }"><span class="row-number">{{ $index + 1 }}</span></template></ElTableColumn>
          <ElTableColumn label="费用日期" width="145"><template #default="{ row }"><ElDatePicker v-model="row.expense_date" type="date" value-format="YYYY-MM-DD" :clearable="false" /></template></ElTableColumn>
          <ElTableColumn label="费用类别" min-width="170"><template #default="{ row }"><ElSelect v-model="row.category" filterable allow-create><ElOption v-for="category in config.expense_categories" :key="category" :label="category" :value="category" /></ElSelect></template></ElTableColumn>
          <ElTableColumn label="金额" width="140"><template #default="{ row }"><ElInputNumber v-model="row.amount" :min="0" :precision="2" :controls="false"><template #prefix>¥</template></ElInputNumber></template></ElTableColumn>
          <ElTableColumn label="关联单号" min-width="180"><template #default="{ row }"><ElInput v-model="row.related_number" placeholder="订单/快递/退货单号" clearable /></template></ElTableColumn>
          <ElTableColumn label="费用说明" min-width="210"><template #default="{ row, $index }"><ElInput v-model="row.description" placeholder="具体用途（选填）" clearable @keyup.enter="addRow($index)" /></template></ElTableColumn>
          <ElTableColumn label="操作" width="90" fixed="right"><template #default="{ $index }"><ElButton text :icon="CopyDocument" title="复制本行" @click="copyRow($index)" /><ElButton text type="danger" :icon="Delete" title="删除本行" @click="removeRow($index)" /></template></ElTableColumn>
        </ElTable>
        <div class="entry-footer"><ElButton text type="primary" :icon="Plus" @click="addRow()">添加一行</ElButton><div>共 {{ form.items.length }} 条明细 <span>合计</span><strong>¥ {{ formatMoney(totalAmount) }}</strong></div></div>
      </section>

      <section class="editor-section attachment-section">
        <div class="section-heading"><div><h3>凭证附件</h3><p>支持图片、PDF、XLSX；可直接在此页面按 Ctrl+V 粘贴微信截图。</p></div><ElUpload multiple :auto-upload="false" :show-file-list="false" accept=".jpg,.jpeg,.png,.webp,.pdf,.xlsx" :on-change="onAttachmentChange"><ElButton :loading="uploading" :icon="Paperclip">选择附件</ElButton></ElUpload></div>
        <div v-if="existingAttachments.length" class="attachment-list">
          <a v-for="item in existingAttachments" :key="item.id" :href="item.url" target="_blank" rel="noreferrer" class="attachment-item"><div class="file-icon"><Paperclip /></div><div><strong>{{ item.original_name }}</strong><span>{{ formatSize(item.size_bytes) }}</span></div><ElButton text type="danger" :icon="Close" @click.prevent="removeAttachment(item)" /></a>
        </div>
        <ElEmpty v-else :image-size="46" description="暂无附件，可选择文件或直接粘贴截图" />
      </section>
    </div>
    <template #footer><div class="drawer-footer"><ElButton v-if="editorId" type="danger" text :icon="Delete" @click="removeDraft">删除草稿</ElButton><span v-else /><div><ElButton @click="editorVisible = false">稍后填写</ElButton><ElButton :loading="editorSaving" @click="saveDraft()">保存草稿</ElButton><ElButton type="primary" :loading="submitting" :icon="Check" @click="submit">提交主管审批</ElButton></div></div></template>
  </ElDrawer>

  <ElDrawer v-model="detailVisible" size="min(780px, 92vw)" title="报销单详情">
    <div v-loading="detailLoading" class="detail-content"><template v-if="detail">
      <section class="detail-hero"><div><span>{{ detail.number }}</span><h2>¥ {{ formatMoney(detail.total_amount) }}</h2><p>{{ detail.applicant_name }} · {{ detail.team }} · {{ detail.item_count }} 条明细</p></div><ElTag :type="statusType(detail)" size="large" effect="light" round>{{ detail.status_label }}</ElTag></section>
      <section class="detail-block"><div class="block-title"><h3>费用明细</h3><span>合计 ¥ {{ formatMoney(detail.total_amount) }}</span></div><ElTable :data="detail.items || []" size="small"><ElTableColumn prop="expense_date" label="日期" width="105" /><ElTableColumn prop="category" label="类别" min-width="130" /><ElTableColumn prop="related_number" label="关联单号" min-width="150" show-overflow-tooltip /><ElTableColumn prop="description" label="说明" min-width="140" show-overflow-tooltip /><ElTableColumn label="金额" width="110" align="right"><template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template></ElTableColumn></ElTable><div v-if="detail.note" class="detail-note"><span>整单说明</span>{{ detail.note }}</div></section>
      <section class="detail-block"><div class="block-title"><h3>凭证附件</h3><span>{{ detail.attachment_count }} 个</span></div><div v-if="detail.attachments?.length" class="detail-files"><a v-for="item in detail.attachments" :key="item.id" :href="item.url" target="_blank" rel="noreferrer"><Paperclip />{{ item.original_name }}</a></div><ElEmpty v-else :image-size="40" description="未上传附件" /></section>
      <section class="detail-block"><div class="block-title"><h3>审批记录</h3><span>{{ detail.approval_records?.length || 0 }} 条</span></div><ElTimeline class="approval-timeline"><ElTimelineItem v-for="record in [...(detail.approval_records || [])].reverse()" :key="record.id" :timestamp="formatDateTime(record.created_at)" placement="top" :type="record.action === 'return' ? 'danger' : record.action.includes('approve') ? 'success' : 'primary'"><strong>{{ approvalTitle(record) }}</strong><p>{{ record.actor_name }}<template v-if="record.comment"> · {{ record.comment }}</template></p></ElTimelineItem></ElTimeline></section>
    </template></div>
    <template v-if="detail" #footer><div class="detail-footer"><ElButton v-if="detail.can_edit" :icon="Edit" @click="openEdit(detail)">编辑报销单</ElButton><span v-else /><div v-if="detail.can_approve"><ElButton type="danger" plain @click="returnCurrent">退回修改</ElButton><ElButton type="primary" :icon="Check" @click="approveCurrent">审批通过</ElButton></div></div></template>
  </ElDrawer>

  <ElDialog v-model="batchVisible" title="Excel 批量导入报销" width="900px" :close-on-click-modal="false">
    <div class="batch-guide">
      <div><span>1</span><strong>下载模板</strong><small>按报销分组填写</small></div>
      <i />
      <div><span>2</span><strong>上传并校验</strong><small>发现错误不会写入</small></div>
      <i />
      <div><span>3</span><strong>批量生成</strong><small>一次生成多张报销单</small></div>
    </div>

    <ElUpload
      drag
      :auto-upload="false"
      :show-file-list="false"
      accept=".xlsx"
      :on-change="onBatchFileChange"
      class="batch-upload"
    >
      <ElIcon class="el-icon--upload"><UploadFilled /></ElIcon>
      <div class="el-upload__text">拖入填写好的批量模板，或<em>点击选择 Excel</em></div>
      <template #tip><div class="el-upload__tip">仅支持系统模板生成的 .xlsx 文件，单次最多 500 行、100 张报销单。</div></template>
    </ElUpload>

    <div v-if="batchFileName" class="batch-file-line">
      <div><CopyDocument /><strong>{{ batchFileName }}</strong></div>
      <span v-if="batchPreviewing">正在读取并校验…</span>
      <ElTag v-else-if="batchPreview?.can_import" type="success" effect="light">校验通过</ElTag>
      <ElTag v-else-if="batchPreview" type="danger" effect="light">需要修改</ElTag>
    </div>

    <template v-if="batchPreview">
      <div class="batch-summary">
        <div><span>报销单</span><strong>{{ batchPreview.claim_count }}</strong></div>
        <div><span>费用明细</span><strong>{{ batchPreview.item_count }}</strong></div>
        <div><span>合计金额</span><strong>¥ {{ formatMoney(batchPreview.total_amount) }}</strong></div>
      </div>

      <ElAlert
        v-if="batchPreview.errors.length"
        type="error"
        :closable="false"
        show-icon
        class="batch-errors"
      >
        <template #title>发现 {{ batchPreview.errors.length }} 个问题，请修改 Excel 后重新上传</template>
        <div v-for="(error, index) in batchPreview.errors.slice(0, 6)" :key="index">
          {{ error.row ? `第 ${error.row} 行` : `分组 ${error.group}` }}：{{ error.message }}
        </div>
      </ElAlert>

      <ElTable :data="batchPreview.claims" border max-height="280" class="batch-preview-table">
        <ElTableColumn prop="group_key" label="报销分组" width="120" />
        <ElTableColumn prop="applicant_name" label="报销人" min-width="120" />
        <ElTableColumn prop="team" label="所属组" width="100" />
        <ElTableColumn prop="item_count" label="明细" width="80" align="center" />
        <ElTableColumn label="合计金额" width="140" align="right"><template #default="{ row }">¥ {{ formatMoney(row.total_amount) }}</template></ElTableColumn>
        <ElTableColumn label="校验" width="110" align="center"><template #default="{ row }"><ElTag :type="row.valid ? 'success' : 'danger'" effect="light">{{ row.valid ? '可导入' : '有问题' }}</ElTag></template></ElTableColumn>
      </ElTable>

      <div class="batch-submit-option">
        <ElCheckbox v-model="batchSubmit">导入后直接提交主管审批</ElCheckbox>
        <span>{{ batchSubmit ? '生成后立即进入待主管审批' : '默认先生成草稿，确认后再逐张提交' }}</span>
      </div>
    </template>

    <template #footer>
      <div class="batch-footer">
        <ElButton tag="a" href="/api/v1/reimbursements/batch/template/xlsx" :icon="Download">下载初始模板</ElButton>
        <div><ElButton @click="batchVisible = false">取消</ElButton><ElButton type="primary" :loading="batchImporting" :disabled="!batchPreview?.can_import" @click="confirmBatchImport">确认批量导入</ElButton></div>
      </div>
    </template>
  </ElDialog>

  <ElDialog v-model="pasteVisible" title="从 Excel 粘贴明细" width="720px">
    <div class="paste-tip"><CopyDocument /><div><strong>复制 Excel 中的多行数据，然后粘贴到下方</strong><p>列顺序：费用日期、费用类别、金额、关联单号、费用说明。第一行表头可以保留。</p></div></div>
    <ElInput v-model="pasteText" type="textarea" :rows="10" placeholder="在这里按 Ctrl+V 粘贴…" />
    <template #footer><ElButton @click="pasteVisible = false">取消</ElButton><ElButton type="primary" @click="applyPaste">识别并填入</ElButton></template>
  </ElDialog>

  <ElDialog v-model="configVisible" title="报销流程设置" width="560px">
    <div class="flow-preview"><div><span>1</span><strong>员工提交</strong></div><i /><div><span>2</span><strong>主管审批</strong></div><i /><div :class="{ disabled: !financeApprovalDraft }"><span>3</span><strong>财务审批</strong></div><i /><div><span>✓</span><strong>待导出</strong></div></div>
    <div class="config-row"><div><strong>启用财务审批</strong><p>关闭时，主管通过后直接进入“待导出”；开启后需要财务再次审批。</p></div><ElSwitch v-model="financeApprovalDraft" /></div>
    <ElAlert title="流程设置只影响之后提交的报销单，审批中的单据保持原流程。" type="info" :closable="false" show-icon />
    <template #footer><ElButton @click="configVisible = false">取消</ElButton><ElButton type="primary" :loading="configSaving" @click="saveConfig">保存设置</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.page-actions,.toolbar,.filters,.quick-actions,.section-heading,.drawer-title,.drawer-footer,.detail-footer,.block-title,.config-row{display:flex;align-items:center}.page-actions,.filters,.quick-actions{gap:10px}.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:18px}.summary-grid article{display:flex;align-items:center;gap:15px;padding:20px}.summary-grid span,.summary-grid small{display:block;color:#7d899c;font-size:12px}.summary-grid strong{display:block;margin:6px 0 4px;color:#1b2942;font-size:25px}.summary-grid .money{font-size:20px}.summary-icon{display:grid;width:44px;height:44px;flex:0 0 auto;place-items:center;border-radius:13px}.summary-icon svg{width:20px}.summary-icon.amber{color:#cb7a16;background:#fff4df}.summary-icon.purple{color:#7656d8;background:#f1edff}.summary-icon.green{color:#149467;background:#e6f8f0}.summary-icon.blue{color:#2f6feb;background:#eaf1ff}.table-card{padding:18px}.toolbar{justify-content:space-between;gap:15px;margin-bottom:17px}.filters .el-input{width:245px}.filters .el-select{width:120px}.filters :deep(.el-date-editor){width:250px}.table-money{color:#243653}.drawer-title{width:100%;justify-content:space-between;padding-right:24px}.drawer-title h2{margin:0;color:#17243c;font-size:21px}.drawer-title p{margin:5px 0 0;color:#8390a4;font-size:12px}.editor-content{display:flex;flex-direction:column;gap:16px}.editor-section{padding:21px 23px;border:1px solid #e6ebf3;border-radius:13px;background:#fff}.section-heading{justify-content:space-between;gap:18px;margin-bottom:16px}.section-heading h3,.block-title h3{margin:0;color:#22304a;font-size:15px}.section-heading p{margin:5px 0 0;color:#8995a7;font-size:12px}.basic-grid{display:grid;grid-template-columns:1fr 1fr 2fr;gap:18px}.basic-grid .el-form-item{margin-bottom:0}.basic-grid :deep(.el-select){width:100%}.quick-heading{align-items:flex-start}.entry-table :deep(.el-table__cell){padding:6px 0}.entry-table :deep(.cell){padding:0 6px}.entry-table :deep(.el-date-editor),.entry-table :deep(.el-select),.entry-table :deep(.el-input-number){width:100%}.row-number{display:block;color:#8b97a9;text-align:center}.entry-footer{display:flex;align-items:center;justify-content:space-between;padding:13px 4px 0;color:#7f8b9d;font-size:13px}.entry-footer span{margin-left:22px}.entry-footer strong{margin-left:10px;color:#2f6feb;font-size:20px}.attachment-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.attachment-item{display:flex;align-items:center;gap:10px;min-width:0;padding:10px;border:1px solid #e4eaf2;border-radius:10px;color:inherit;text-decoration:none}.attachment-item:hover{border-color:#aac7f8;background:#f8fbff}.attachment-item>div:nth-child(2){min-width:0;flex:1}.attachment-item strong,.attachment-item span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.attachment-item strong{color:#34425a;font-size:12px}.attachment-item span{margin-top:3px;color:#98a3b3;font-size:11px}.file-icon{display:grid;width:32px;height:32px;flex:0 0 auto;place-items:center;border-radius:8px;color:#2f6feb;background:#edf3ff}.file-icon svg{width:15px}.drawer-footer,.detail-footer{justify-content:space-between}.detail-content{min-height:300px}.detail-hero{display:flex;align-items:flex-start;justify-content:space-between;padding:23px;border-radius:14px;color:#fff;background:linear-gradient(135deg,#163761,#225ca8)}.detail-hero span{font-size:12px;opacity:.78}.detail-hero h2{margin:8px 0 5px;font-size:30px}.detail-hero p{margin:0;font-size:13px;opacity:.82}.detail-block{margin-top:15px;padding:20px;border:1px solid #e6ebf3;border-radius:13px}.block-title{justify-content:space-between;margin-bottom:14px}.block-title span{color:#78869b;font-size:12px}.detail-note{margin-top:12px;padding:10px 12px;border-radius:8px;color:#5e6b7e;background:#f6f8fb;font-size:12px}.detail-note span{margin-right:12px;color:#8b97a8}.detail-files{display:flex;flex-wrap:wrap;gap:8px}.detail-files a{display:flex;align-items:center;gap:6px;padding:8px 10px;border:1px solid #e2e8f1;border-radius:8px;color:#2f6feb;font-size:12px;text-decoration:none}.detail-files svg{width:14px}.approval-timeline{padding-top:4px}.approval-timeline strong{color:#34425a;font-size:13px}.approval-timeline p{margin:4px 0 0;color:#8290a4;font-size:12px}.paste-tip{display:flex;gap:12px;margin-bottom:14px;padding:13px;border-radius:10px;color:#506078;background:#f3f7fd}.paste-tip svg{width:23px;color:#2f6feb}.paste-tip strong{font-size:13px}.paste-tip p{margin:4px 0 0;font-size:12px}.flow-preview{display:flex;align-items:center;justify-content:center;margin-bottom:24px;padding:18px;border-radius:11px;background:#f5f8fc}.flow-preview div{display:flex;align-items:center;gap:6px}.flow-preview div span{display:grid;width:24px;height:24px;place-items:center;border-radius:50%;color:#fff;background:#2f6feb;font-size:11px}.flow-preview div strong{font-size:12px;white-space:nowrap}.flow-preview i{width:25px;height:1px;margin:0 7px;background:#cbd5e4}.flow-preview .disabled{opacity:.38}.config-row{justify-content:space-between;margin-bottom:18px;padding:16px;border:1px solid #e5eaf2;border-radius:10px}.config-row strong{color:#2d3a51;font-size:14px}.config-row p{max-width:400px;margin:6px 0 0;color:#8793a5;font-size:12px;line-height:1.6}@media(max-width:1200px){.summary-grid{grid-template-columns:repeat(2,1fr)}.toolbar{align-items:flex-start;flex-direction:column}.filters{width:100%;flex-wrap:wrap}.attachment-list{grid-template-columns:repeat(2,1fr)}}@media(max-width:760px){.summary-grid{grid-template-columns:1fr}.page-actions,.filters,.quick-actions{flex-wrap:wrap}.basic-grid{grid-template-columns:1fr}.attachment-list{grid-template-columns:1fr}.section-heading{align-items:flex-start;flex-direction:column}.flow-preview{overflow-x:auto;justify-content:flex-start}}
.batch-guide{display:flex;align-items:center;justify-content:center;margin-bottom:18px;padding:15px 18px;border-radius:11px;background:#f5f8fc}.batch-guide>div{display:grid;grid-template-columns:28px auto;gap:1px 8px;align-items:center}.batch-guide>div span{grid-row:1/3;display:grid;width:28px;height:28px;place-items:center;border-radius:50%;color:#fff;background:#2f6feb;font-size:12px}.batch-guide strong{color:#33425a;font-size:13px}.batch-guide small{color:#8a96a8;font-size:11px}.batch-guide i{width:42px;height:1px;margin:0 18px;background:#cbd5e4}.batch-upload :deep(.el-upload-dragger){padding:24px}.batch-file-line,.batch-file-line>div,.batch-submit-option,.batch-footer{display:flex;align-items:center}.batch-file-line{justify-content:space-between;margin-top:13px;padding:11px 14px;border:1px solid #e5eaf2;border-radius:9px;background:#fbfcfe}.batch-file-line>div{gap:8px;min-width:0}.batch-file-line svg{width:16px;color:#2f6feb}.batch-file-line strong{overflow:hidden;color:#35445c;font-size:12px;text-overflow:ellipsis;white-space:nowrap}.batch-file-line>span{color:#7c899d;font-size:12px}.batch-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}.batch-summary>div{padding:13px 15px;border:1px solid #e4eaf2;border-radius:9px;background:#f8fafd}.batch-summary span{display:block;color:#8793a5;font-size:11px}.batch-summary strong{display:block;margin-top:5px;color:#263650;font-size:18px}.batch-errors{margin-top:14px}.batch-errors :deep(.el-alert__content){width:100%}.batch-errors :deep(.el-alert__description){line-height:1.65}.batch-preview-table{margin-top:14px}.batch-submit-option{justify-content:space-between;margin-top:14px;padding:12px 14px;border-radius:9px;background:#f4f7fb}.batch-submit-option span{color:#8491a4;font-size:12px}.batch-footer{justify-content:space-between}.batch-footer>div{display:flex;gap:9px}@media(max-width:760px){.batch-guide{align-items:flex-start;flex-direction:column;gap:10px}.batch-guide i{display:none}.batch-summary{grid-template-columns:1fr}.batch-submit-option{align-items:flex-start;flex-direction:column;gap:8px}.batch-footer{align-items:stretch;flex-direction:column;gap:10px}.batch-footer>div{justify-content:flex-end}}
</style>
