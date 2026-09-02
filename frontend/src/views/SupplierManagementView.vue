<script setup lang="ts">
import {
  Download,
  Edit,
  OfficeBuilding,
  Plus,
  Search,
  SwitchButton,
  UploadFilled,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  createSupplier,
  downloadSupplierTemplate,
  exportSuppliers,
  getSupplierChanges,
  getSuppliers,
  importSuppliers,
  updateSupplier,
  updateSupplierStatus,
  type SupplierChangeRecord,
  type SupplierPayload,
  type SupplierRecord,
} from '../api/suppliers'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const currentMonth = new Date().toISOString().slice(0, 7)
const month = ref(currentMonth)
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const exporting = ref(false)
const records = ref<SupplierRecord[]>([])
const changes = ref<SupplierChangeRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const keyword = ref('')
const statusFilter = ref<'' | 'active' | 'inactive'>('')
const activeTab = ref('records')
const dialogVisible = ref(false)
const editId = ref<number>()
const importFileInput = ref<HTMLInputElement>()
let searchTimer: number | undefined

const summary = reactive({ total: 0, active: 0, inactive: 0, month_added: 0, month_changed: 0 })
const emptyForm = (): SupplierPayload => ({
  name: '',
  contact_name: '',
  contact_phone: '',
  address: '',
  cooperation_start_date: null,
  product_types: '',
  note: '',
  change_month: month.value,
  change_note: '',
})
const form = reactive<SupplierPayload>(emptyForm())

const canManage = computed(() => auth.can('suppliers.manage'))

function errorText(error: unknown) {
  return (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    || '操作失败，请稍后重试'
}

function formatTime(value: string) {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 16)
}

function productList(value: string) {
  return value.split(/[,，、]/).map((item) => item.trim()).filter(Boolean).slice(0, 4)
}

function changeLabel(type: SupplierChangeRecord['change_type']) {
  return {
    created: '新增',
    updated: '资料更新',
    activated: '恢复合作',
    deactivated: '停止合作',
  }[type]
}

function changeTagType(type: SupplierChangeRecord['change_type']) {
  if (type === 'created' || type === 'activated') return 'success'
  if (type === 'deactivated') return 'danger'
  return 'primary'
}

async function loadRecords() {
  loading.value = true
  try {
    const data = await getSuppliers({
      keyword: keyword.value.trim() || undefined,
      active: statusFilter.value === '' ? undefined : statusFilter.value === 'active',
      month: month.value,
      page: page.value,
      size: pageSize.value,
    })
    records.value = data.records
    total.value = data.total
    Object.assign(summary, data.summary)
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    loading.value = false
  }
}

async function loadChanges() {
  try {
    changes.value = await getSupplierChanges(month.value)
  } catch (error) {
    ElMessage.error(errorText(error))
  }
}

async function refreshAll() {
  await Promise.all([loadRecords(), loadChanges()])
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
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row: SupplierRecord) {
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    contact_name: row.contact_name,
    contact_phone: row.contact_phone,
    address: row.address,
    cooperation_start_date: row.cooperation_start_date || null,
    product_types: row.product_types,
    note: row.note,
    change_month: month.value,
    change_note: '',
  })
  dialogVisible.value = true
}

async function submit() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入供应商名称')
    return
  }
  saving.value = true
  try {
    if (editId.value) await updateSupplier(editId.value, form)
    else await createSupplier(form)
    dialogVisible.value = false
    ElMessage.success(editId.value ? '供应商资料已更新' : '供应商已新增')
    await refreshAll()
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row: SupplierRecord) {
  const nextActive = !row.is_active
  const action = nextActive ? '恢复合作' : '停止合作'
  try {
    await ElMessageBox.confirm(
      `确定将“${row.name}”标记为${action}吗？本次变化将计入 ${month.value}。`,
      `${action}确认`,
      { type: nextActive ? 'success' : 'warning', confirmButtonText: action },
    )
    await updateSupplierStatus(row.id, {
      is_active: nextActive,
      change_month: month.value,
      change_note: action,
    })
    ElMessage.success(`已${action}`)
    await refreshAll()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error))
  }
}

function saveBlob(
  response: { data: Blob; headers: Record<string, unknown> },
  fallbackName: string,
) {
  const disposition = String(response.headers['content-disposition'] || '')
  const match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  const filename = match?.[1] ? decodeURIComponent(match[1]) : fallbackName
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
    const response = await downloadSupplierTemplate()
    saveBlob(response, '供应商导入模板.xlsx')
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
    ElMessage.warning('请选择 .xlsx 格式的供应商导入表')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将按供应商名称匹配：同名更新，未匹配新增。本次变化统一计入 ${month.value}，是否继续？`,
      '导入供应商确认',
      { type: 'info', confirmButtonText: '开始导入' },
    )
    importing.value = true
    const result = await importSuppliers(file, month.value)
    ElMessage.success(
      `导入完成：新增 ${result.created_count} 家，更新 ${result.updated_count} 家，跳过 ${result.skipped_count} 家`,
    )
    await refreshAll()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(errorText(error))
  } finally {
    importing.value = false
  }
}

async function exportCurrentSuppliers() {
  exporting.value = true
  try {
    const response = await exportSuppliers({
      keyword: keyword.value.trim() || undefined,
      active: statusFilter.value === '' ? undefined : statusFilter.value === 'active',
    })
    saveBlob(response, `供应商档案_${new Date().toISOString().slice(0, 10)}.xlsx`)
    ElMessage.success('已导出当前筛选范围的供应商档案')
  } catch (error) {
    ElMessage.error(errorText(error))
  } finally {
    exporting.value = false
  }
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
  page.value = 1
  await refreshAll()
})
watch(statusFilter, async () => {
  page.value = 1
  await loadRecords()
})
onMounted(refreshAll)
</script>

<template>
  <div class="page-heading supplier-heading">
    <div>
      <h1>供应商管理</h1>
      <p>统一维护供应商主档和月度变更，经营分析将直接读取这里的数据。</p>
    </div>
    <div class="heading-actions">
      <div class="month-control">
        <span>变更月份</span>
        <ElDatePicker
          v-model="month"
          type="month"
          value-format="YYYY-MM"
          format="YYYY年MM月"
          :clearable="false"
        />
      </div>
      <ElButton v-if="canManage" type="primary" :icon="Plus" @click="openCreate">新增供应商</ElButton>
    </div>
  </div>

  <section class="summary-grid">
    <article class="surface-card summary-card total">
      <div class="summary-icon"><OfficeBuilding /></div>
      <div><span>供应商总数</span><strong>{{ summary.total }}</strong><small>全部主档</small></div>
    </article>
    <article class="surface-card summary-card active">
      <div class="summary-dot" />
      <div><span>合作中</span><strong>{{ summary.active }}</strong><small>{{ summary.inactive }} 家已停用</small></div>
    </article>
    <article class="surface-card summary-card added">
      <div><span>本月新增</span><strong>{{ summary.month_added }}</strong><small>{{ month }} 新建主档</small></div>
    </article>
    <article class="surface-card summary-card changed">
      <div><span>本月变化</span><strong>{{ summary.month_changed }}</strong><small>按供应商去重</small></div>
    </article>
  </section>

  <section class="surface-card supplier-card">
    <ElTabs v-model="activeTab" class="supplier-tabs">
      <ElTabPane label="供应商档案" name="records">
        <div class="table-toolbar">
          <ElInput
            v-model="keyword"
            :prefix-icon="Search"
            clearable
            placeholder="搜索供应商、联系人、电话或产品"
            @input="scheduleSearch"
          />
          <ElSelect v-model="statusFilter" aria-label="合作状态">
            <ElOption label="全部状态" value="" />
            <ElOption label="合作中" value="active" />
            <ElOption label="已停用" value="inactive" />
          </ElSelect>
          <div class="toolbar-summary">共 <strong>{{ total }}</strong> 家供应商</div>
          <div class="toolbar-actions">
            <ElButton v-if="canManage" :icon="Download" @click="handleExcelCommand('template')">
              下载模板
            </ElButton>
            <ElButton
              v-if="canManage"
              :icon="UploadFilled"
              :loading="importing"
              @click="handleExcelCommand('import')"
            >
              Excel 批量上传
            </ElButton>
            <ElButton
              :icon="Download"
              :loading="exporting"
              :disabled="total === 0"
              type="primary"
              plain
              @click="exportCurrentSuppliers"
            >
              导出数据
            </ElButton>
          </div>
          <input
            ref="importFileInput"
            class="visually-hidden"
            type="file"
            accept=".xlsx"
            @change="handleImportFile"
          />
        </div>

        <ElTable v-loading="loading" :data="records" border stripe row-key="id" class="supplier-table">
          <ElTableColumn type="index" label="序号" width="66" :index="(index: number) => (page - 1) * pageSize + index + 1" />
          <ElTableColumn prop="name" label="供应商名称" min-width="180" fixed="left">
            <template #default="{ row }"><strong class="supplier-name">{{ row.name }}</strong></template>
          </ElTableColumn>
          <ElTableColumn prop="contact_name" label="供应商联系人" min-width="130">
            <template #default="{ row }">{{ row.contact_name || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="contact_phone" label="联系电话" min-width="140">
            <template #default="{ row }">{{ row.contact_phone || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="address" label="联系地址" min-width="190" show-overflow-tooltip>
            <template #default="{ row }">{{ row.address || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="cooperation_start_date" label="合作时间" width="120">
            <template #default="{ row }">{{ row.cooperation_start_date || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="product_types" label="常用产品类型" min-width="210">
            <template #default="{ row }">
              <div v-if="productList(row.product_types).length" class="product-tags">
                <ElTag v-for="item in productList(row.product_types)" :key="item" effect="plain" size="small">{{ item }}</ElTag>
              </div>
              <span v-else>—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="100" align="center">
            <template #default="{ row }">
              <ElTag :type="row.is_active ? 'success' : 'info'" effect="light">
                {{ row.is_active ? '合作中' : '已停用' }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="最后更新" width="150">
            <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
          </ElTableColumn>
          <ElTableColumn v-if="canManage" label="操作" width="150" fixed="right" align="center">
            <template #default="{ row }">
              <ElButton text type="primary" :icon="Edit" @click="openEdit(row)">编辑</ElButton>
              <ElButton text :type="row.is_active ? 'danger' : 'success'" :icon="SwitchButton" @click="toggleStatus(row)">
                {{ row.is_active ? '停用' : '启用' }}
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
        <ElEmpty v-if="!records.length && !loading" description="暂无符合条件的供应商" />
        <ElPagination
          v-if="total > 0"
          class="pagination"
          background
          layout="total, sizes, prev, pager, next, jumper"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[50, 100, 200]"
          :total="total"
          @current-change="changePage"
          @size-change="changePageSize"
        />
      </ElTabPane>

      <ElTabPane :label="`${month} 变更记录`" name="changes">
        <ElAlert
          class="history-hint"
          type="info"
          :closable="false"
          show-icon
          title="新增、资料修改和启停都会留痕；经营分析按本月发生变化的供应商去重展示。"
        />
        <ElTable :data="changes" border stripe class="history-table">
          <ElTableColumn prop="created_at" label="操作时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="supplier_name" label="供应商名称" min-width="190" />
          <ElTableColumn prop="change_type" label="变化类型" width="120" align="center">
            <template #default="{ row }">
              <ElTag :type="changeTagType(row.change_type)" effect="light">{{ changeLabel(row.change_type) }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="operator_name" label="操作人" width="130" />
          <ElTableColumn prop="change_note" label="变更说明" min-width="220">
            <template #default="{ row }">{{ row.change_note || '—' }}</template>
          </ElTableColumn>
        </ElTable>
        <ElEmpty v-if="!changes.length" :description="`${month} 暂无供应商变化`" />
      </ElTabPane>
    </ElTabs>
  </section>

  <ElDialog v-model="dialogVisible" :title="editId ? '编辑供应商' : '新增供应商'" width="720px" destroy-on-close>
    <ElForm label-position="top">
      <div class="form-grid">
        <ElFormItem label="供应商名称" required><ElInput v-model="form.name" maxlength="160" /></ElFormItem>
        <ElFormItem label="供应商联系人"><ElInput v-model="form.contact_name" maxlength="100" /></ElFormItem>
        <ElFormItem label="联系电话"><ElInput v-model="form.contact_phone" maxlength="50" /></ElFormItem>
        <ElFormItem label="联系地址"><ElInput v-model="form.address" maxlength="255" /></ElFormItem>
        <ElFormItem label="合作时间">
          <ElDatePicker v-model="form.cooperation_start_date" type="date" value-format="YYYY-MM-DD" format="YYYY年MM月DD日" clearable />
        </ElFormItem>
        <ElFormItem label="常用产品类型">
          <ElInput v-model="form.product_types" maxlength="500" placeholder="多个类型可用逗号分隔" />
        </ElFormItem>
        <ElFormItem label="供应商备注" class="span-2">
          <ElInput v-model="form.note" type="textarea" :rows="2" maxlength="1000" show-word-limit />
        </ElFormItem>
      </div>
      <div class="change-box">
        <ElFormItem label="本次变更计入月份" required>
          <ElDatePicker v-model="form.change_month" type="month" value-format="YYYY-MM" format="YYYY年MM月" :clearable="false" />
        </ElFormItem>
        <ElFormItem label="本次变更说明">
          <ElInput v-model="form.change_note" maxlength="500" placeholder="例如：联系人变更、增加新品类" />
        </ElFormItem>
      </div>
    </ElForm>
    <template #footer>
      <ElButton @click="dialogVisible = false">取消</ElButton>
      <ElButton type="primary" :loading="saving" @click="submit">保存</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.supplier-heading { align-items:flex-end; }
.heading-actions { display:flex; align-items:flex-end; gap:10px; }
.month-control span { display:block; margin-bottom:6px; color:#7b8799; font-size:10px; }
.summary-grid { display:grid; margin-bottom:18px; grid-template-columns:repeat(4,minmax(0,1fr)); gap:15px; }
.summary-card { display:flex; min-height:112px; padding:20px 22px; align-items:center; gap:15px; }
.summary-card>div:last-child { min-width:0; }
.summary-card span { color:#7e8b9f; font-size:11px; }
.summary-card strong { display:block; margin:5px 0 3px; color:#1f304c; font-size:25px; }
.summary-card small { color:#98a3b3; font-size:10px; }
.summary-icon { display:grid; width:42px; height:42px; flex:none; place-items:center; border-radius:12px; color:#2f6feb; background:#eaf1ff; }
.summary-icon svg { width:21px; }
.summary-dot { width:12px; height:12px; flex:none; border:4px solid #dff5e9; border-radius:50%; background:#35ad72; box-sizing:content-box; }
.summary-card.added { border-top:3px solid #6cb58b; }
.summary-card.changed { border-top:3px solid #6894dc; }
.supplier-card { padding:18px 20px 20px; }
.supplier-tabs :deep(.el-tabs__header) { margin-bottom:17px; }
.table-toolbar { display:flex; margin-bottom:14px; align-items:center; gap:10px; }
.table-toolbar :deep(.el-input) { width:min(390px,100%); }
.table-toolbar :deep(.el-select) { width:130px; }
.toolbar-summary { margin-left:auto; color:#8490a2; font-size:11px; white-space:nowrap; }
.table-toolbar strong { color:#2f6feb; }
.toolbar-actions { display:flex; align-items:center; gap:9px; }
.toolbar-actions :deep(.el-button svg) { width:14px; margin-right:5px; }
.visually-hidden { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); clip-path:inset(50%); white-space:nowrap; }
.supplier-table { width:100%; overflow:hidden; border-radius:10px 10px 0 0; }
.supplier-table :deep(th.el-table__cell) { color:#304766; background:#f1f6ff !important; }
.supplier-name { color:#263a58; }
.product-tags { display:flex; flex-wrap:wrap; gap:5px; }
.pagination { display:flex; margin-top:18px; padding-top:16px; justify-content:flex-end; border-top:1px solid #e8edf4; }
.history-hint { margin-bottom:14px; }
.history-table { border-radius:10px; overflow:hidden; }
.form-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 18px; }
.span-2 { grid-column:1 / -1; }
.form-grid :deep(.el-date-editor),.change-box :deep(.el-date-editor) { width:100%; }
.change-box { display:grid; margin-top:4px; padding:15px 16px 0; grid-template-columns:200px minmax(0,1fr); gap:18px; border:1px solid #dce8f8; border-radius:10px; background:#f7faff; }
@media(max-width:1000px){.summary-grid{grid-template-columns:repeat(2,1fr)}.table-toolbar{align-items:stretch;flex-wrap:wrap}.toolbar-summary{margin-left:auto}.toolbar-actions{width:100%;justify-content:flex-end}}
@media(max-width:720px){.supplier-heading,.heading-actions{align-items:stretch;flex-direction:column}.summary-grid,.form-grid,.change-box{grid-template-columns:1fr}.span-2{grid-column:auto}.pagination{overflow-x:auto;justify-content:flex-start}}
</style>
