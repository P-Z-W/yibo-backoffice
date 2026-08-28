<script setup lang="ts">
import { Delete, Download, Edit, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { addSalary, deleteSalary, getSalary, saveSalary, type SalaryPayload, type SalaryRecord } from '../api/salary'
import { formatCount } from '../utils/format'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const month = ref(new Date().toISOString().slice(0, 7))
const loading = ref(false)
const records = ref<SalaryRecord[]>([])
const summary = reactive({ employees: 0, base_salary: 0, bonus: 0, deduction: 0, total: 0 })
const dialog = ref(false)
const editId = ref<number>()
const form = reactive<SalaryPayload>({ name: '', team: '', year_month: month.value, base_salary: 0, bonus: 0, deduction: 0, note: '' })
const formTotal = computed(() => Number(form.base_salary) + Number(form.bonus) - Number(form.deduction))

async function load() {
  loading.value = true
  try { const data = await getSalary(month.value); records.value = data.records; Object.assign(summary, data.summary) } finally { loading.value = false }
}
function openAdd() { editId.value = undefined; Object.assign(form, { name:'', team:'', year_month:month.value, base_salary:0, bonus:0, deduction:0, note:'' }); dialog.value = true }
function openEdit(row: SalaryRecord) { editId.value = row.id; Object.assign(form, row); dialog.value = true }
async function submit() { if (!form.name.trim()) return ElMessage.warning('请输入员工姓名'); if (editId.value) await saveSalary(editId.value, form); else await addSalary(form); dialog.value=false; await load(); ElMessage.success('工资记录已保存') }
async function remove(row: SalaryRecord) { await ElMessageBox.confirm(`确定删除 ${row.name} 的工资记录吗？`, '删除确认', { type:'warning' }); await deleteSalary(row.id); await load() }

watch(month, load)
onMounted(load)
</script>

<template>
  <div class="page-heading"><div><h1>员工工资</h1><p>工资管理能力已完整迁入新数据库。</p></div><div class="actions"><ElDatePicker v-model="month" type="month" value-format="YYYY-MM" format="YYYY年MM月" :clearable="false" /><ElButton v-if="auth.can('salary.export')" tag="a" :href="`/api/v1/salary/export/xlsx?month=${month}`" :icon="Download">导出</ElButton><ElButton v-if="auth.can('salary.manage')" type="primary" :icon="Plus" @click="openAdd">新增记录</ElButton></div></div>
  <section class="summary-grid"><article class="surface-card"><span>员工数</span><strong>{{ summary.employees }}</strong></article><article class="surface-card"><span>基本工资</span><strong>¥ {{ formatCount(summary.base_salary) }}</strong></article><article class="surface-card"><span>绩效奖金</span><strong>¥ {{ formatCount(summary.bonus) }}</strong></article><article class="surface-card"><span>实发工资</span><strong>¥ {{ formatCount(summary.total) }}</strong></article></section>
  <section class="surface-card table-card" v-loading="loading"><ElTable :data="records" stripe><ElTableColumn prop="name" label="姓名" min-width="120" /><ElTableColumn prop="team" label="团队" min-width="130" /><ElTableColumn prop="year_month" label="月份" width="110" /><ElTableColumn label="基本工资" width="130"><template #default="{row}">¥ {{ formatCount(row.base_salary) }}</template></ElTableColumn><ElTableColumn label="绩效奖金" width="130"><template #default="{row}">¥ {{ formatCount(row.bonus) }}</template></ElTableColumn><ElTableColumn label="扣款" width="120"><template #default="{row}">¥ {{ formatCount(row.deduction) }}</template></ElTableColumn><ElTableColumn label="实发工资" width="140"><template #default="{row}"><strong>¥ {{ formatCount(row.total) }}</strong></template></ElTableColumn><ElTableColumn prop="note" label="备注" min-width="170" show-overflow-tooltip /><ElTableColumn v-if="auth.can('salary.manage')" label="操作" width="110" fixed="right"><template #default="{row}"><ElButton text type="primary" :icon="Edit" @click="openEdit(row)" /><ElButton text type="danger" :icon="Delete" @click="remove(row)" /></template></ElTableColumn></ElTable><ElEmpty v-if="!records.length && !loading" description="该月份暂无工资记录" /></section>

  <ElDialog v-model="dialog" :title="editId ? '编辑工资记录' : '新增工资记录'" width="580px"><ElForm label-position="top"><div class="form-grid"><ElFormItem label="姓名"><ElInput v-model="form.name" /></ElFormItem><ElFormItem label="团队"><ElInput v-model="form.team" /></ElFormItem><ElFormItem label="工资月份"><ElDatePicker v-model="form.year_month" type="month" value-format="YYYY-MM" /></ElFormItem><ElFormItem label="基本工资"><ElInputNumber v-model="form.base_salary" :min="0" :controls="false" /></ElFormItem><ElFormItem label="绩效奖金"><ElInputNumber v-model="form.bonus" :controls="false" /></ElFormItem><ElFormItem label="扣款"><ElInputNumber v-model="form.deduction" :min="0" :controls="false" /></ElFormItem></div><ElFormItem label="备注"><ElInput v-model="form.note" type="textarea" /></ElFormItem><div class="total-line">实发工资 <strong>¥ {{ formatCount(formTotal) }}</strong></div></ElForm><template #footer><ElButton @click="dialog=false">取消</ElButton><ElButton type="primary" @click="submit">保存</ElButton></template></ElDialog>
</template>

<style scoped>
.actions { display:flex; gap:9px; }.summary-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:17px; margin-bottom:18px; }.summary-grid article { padding:22px; }.summary-grid span { color:#7e8a9d; font-size:12px; }.summary-grid strong { display:block; margin-top:10px; color:#1b2942; font-size:23px; }.table-card { padding:18px; }.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:0 18px; }.form-grid :deep(.el-input-number),.form-grid :deep(.el-date-editor){width:100%}.total-line { display:flex; justify-content:flex-end; align-items:center; gap:14px; padding:14px 0; color:#778398; }.total-line strong { color:#2f6feb; font-size:20px; }@media(max-width:800px){.summary-grid{grid-template-columns:repeat(2,1fr)}.actions{flex-wrap:wrap}}
</style>
