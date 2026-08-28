<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import {
  getCarriers,
  getExpressSettings,
  getPriceBook,
  getTeamPrices,
  saveCarriers,
  saveExpressSettings,
  savePriceBook,
  saveTeamPrices,
  type PriceRow,
  type TeamPrice,
} from '../../api/express'

const active = ref('carriers')
const loading = ref(true)
const saving = ref('')
const customers = ref<TeamPrice[]>([])
const customerBaseline = ref('[]')
const carriers = ref<Array<{ name: string; identify_column: string; enabled: boolean }>>([])
const runtime = reactive({ extend_days_before: 15, extend_days_after: 5, process_month: '', sql_start_date: '', sql_end_date: '' })
const prices = reactive<{ shentong: PriceRow[]; zhongtong: PriceRow[]; charge: Array<{ type: string; price: number }> }>({ shentong: [], zhongtong: [], charge: [] })
const customerDirty = computed(() => JSON.stringify(customers.value) !== customerBaseline.value)

function emptyCustomer(): TeamPrice {
  return { team: '', st_fee: 0, st3: 0, st01: 0, zt_fee: 0, zt3: 0, zt01: 0, xixi_1kg_unit_price: null, special_note: '' }
}
function emptyPrice(): PriceRow { return { province: '', fee_3kg: 0, fee_over3kg: 0, unit_price: 0 } }

async function load() {
  loading.value = true
  try {
    const [customerData, carrierData, settingData, priceData] = await Promise.all([getTeamPrices(), getCarriers(), getExpressSettings(), getPriceBook()])
    customers.value = customerData
    customerBaseline.value = JSON.stringify(customerData)
    carriers.value = carrierData.map(({ name, identify_column, enabled }) => ({ name, identify_column, enabled }))
    Object.assign(runtime, settingData)
    Object.assign(prices, priceData)
  } finally { loading.value = false }
}

async function removeCustomer(index: number) {
  await ElMessageBox.confirm('删除后需保存客户配置才会写入新系统数据库。是否确认删除？', '确认删除客户配置', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
  customers.value.splice(index, 1)
}

async function saveSection(section: string) {
  saving.value = section
  try {
    if (section === 'carriers') await saveCarriers(carriers.value)
    if (section === 'shentong' || section === 'zhongtong' || section === 'charge') await savePriceBook(prices)
    if (section === 'runtime') await saveExpressSettings(runtime.extend_days_before, runtime.extend_days_after)
    if (section === 'customers') {
      const rows = customers.value.filter((item) => item.team.trim())
      await saveTeamPrices(rows)
      customers.value = rows
      customerBaseline.value = JSON.stringify(rows)
    }
    ElMessage.success('保存成功')
  } finally { saving.value = '' }
}

async function confirmCustomerLeave() {
  if (!customerDirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，是否先保存再离开？', '客户配置尚未保存', {
      confirmButtonText: '保存并离开', cancelButtonText: '不保存并离开', distinguishCancelAndClose: true, closeOnClickModal: false,
    })
    await saveSection('customers')
    return true
  } catch (action) {
    if (action === 'cancel') {
      customers.value = JSON.parse(customerBaseline.value) as TeamPrice[]
      return true
    }
    return false
  }
}

async function beforeTabLeave(_newName: string | number, oldName: string | number) {
  return oldName !== 'customers' || await confirmCustomerLeave()
}

onBeforeRouteLeave(async () => await confirmCustomerLeave())
onMounted(load)
</script>

<template>
  <div class="legacy-express">
    <h1 class="legacy-page-title"><span class="config-icon">☷</span>系统配置</h1>
    <section class="legacy-card config-card" v-loading="loading">
      <ElTabs v-model="active" :before-leave="beforeTabLeave">
        <ElTabPane label="快递管理" name="carriers">
          <div class="pane-intro"><div><h2>快递公司管理</h2><p>按原始账单表头自动识别快递公司。</p></div><ElButton :icon="Plus" @click="carriers.push({ name:'', identify_column:'', enabled:true })">新增快递</ElButton></div>
          <ElTable :data="carriers" border stripe><ElTableColumn label="快递名称" min-width="170"><template #default="{ row }"><ElInput v-model="row.name" /></template></ElTableColumn><ElTableColumn label="账单识别列" min-width="220"><template #default="{ row }"><ElInput v-model="row.identify_column" /></template></ElTableColumn><ElTableColumn label="启用" width="110" align="center"><template #default="{ row }"><ElSwitch v-model="row.enabled" /></template></ElTableColumn><ElTableColumn label="操作" width="90" align="center"><template #default="{ $index }"><ElButton text type="danger" :icon="Delete" @click="carriers.splice($index, 1)" /></template></ElTableColumn></ElTable>
          <div class="save-bar"><ElButton type="primary" :loading="saving === 'carriers'" @click="saveSection('carriers')">保存快递配置</ElButton></div>
        </ElTabPane>

        <ElTabPane v-for="section in [{ name:'shentong', label:'申通报价' }, { name:'zhongtong', label:'中通报价' }]" :key="section.name" :label="section.label" :name="section.name">
          <div class="pane-intro"><div><h2>{{ section.label }}</h2><p>省份首重、超重面单费和续重单价。</p></div><ElButton :icon="Plus" @click="prices[section.name as 'shentong' | 'zhongtong'].push(emptyPrice())">新增省份</ElButton></div>
          <ElTable :data="prices[section.name as 'shentong' | 'zhongtong']" height="540" border stripe><ElTableColumn label="省份" min-width="150"><template #default="{ row }"><ElInput v-model="row.province" /></template></ElTableColumn><ElTableColumn label="3kg内面单费" min-width="160"><template #default="{ row }"><ElInputNumber v-model="row.fee_3kg" :controls="false" /></template></ElTableColumn><ElTableColumn label="超3kg面单费" min-width="160"><template #default="{ row }"><ElInputNumber v-model="row.fee_over3kg" :controls="false" /></template></ElTableColumn><ElTableColumn label="续重单价" min-width="150"><template #default="{ row }"><ElInputNumber v-model="row.unit_price" :controls="false" /></template></ElTableColumn><ElTableColumn label="操作" width="90" align="center"><template #default="{ $index }"><ElButton text type="danger" :icon="Delete" @click="prices[section.name as 'shentong' | 'zhongtong'].splice($index, 1)" /></template></ElTableColumn></ElTable>
          <div class="save-bar"><ElButton type="primary" :loading="saving === section.name" @click="saveSection(section.name)">保存{{ section.label }}</ElButton></div>
        </ElTabPane>

        <ElTabPane label="充单价格" name="charge">
          <div class="pane-intro"><div><h2>客户快递加收单价</h2><p>按快递类型维护客户充单价格。</p></div></div>
          <div class="charge-list"><div v-for="item in prices.charge" :key="item.type"><b>{{ item.type }}</b><ElInputNumber v-model="item.price" :min="0" :controls="false" /><span>元 / 单</span></div></div>
          <div class="save-bar"><ElButton type="primary" :loading="saving === 'charge'" @click="saveSection('charge')">保存充单价格</ElButton></div>
        </ElTabPane>

        <ElTabPane label="运行参数" name="runtime">
          <div class="pane-intro"><div><h2>订单查询范围</h2><p>围绕处理月份向前、向后扩展数据库查询日期。</p></div></div>
          <div class="runtime-grid"><ElForm label-position="top"><ElFormItem label="查询日期向前扩展"><ElInputNumber v-model="runtime.extend_days_before" :min="0" :max="60" /><span class="unit">天</span></ElFormItem><ElFormItem label="查询日期向后扩展"><ElInputNumber v-model="runtime.extend_days_after" :min="0" :max="60" /><span class="unit">天</span></ElFormItem></ElForm><div class="runtime-info"><span>处理月份</span><strong>{{ runtime.process_month }}</strong><span>数据库查询范围</span><p>{{ runtime.sql_start_date }}<br />至 {{ runtime.sql_end_date }}</p></div></div>
          <div class="save-bar"><ElButton type="primary" :loading="saving === 'runtime'" @click="saveSection('runtime')">保存运行参数</ElButton></div>
        </ElTabPane>

        <ElTabPane label="客户情况" name="customers">
          <div class="pane-intro"><div><h2>客户计费配置</h2><p>修改后必须保存；离开时系统会提示未保存内容。</p></div><div><ElButton disabled>同步云端（规划中）</ElButton><ElButton :icon="Plus" @click="customers.push(emptyCustomer())">新增客户</ElButton></div></div>
          <ElTable :data="customers" height="560" border stripe><ElTableColumn type="index" label="#" width="55" fixed /><ElTableColumn label="团队" min-width="160" fixed><template #default="{ row }"><ElInput v-model="row.team" /></template></ElTableColumn><ElTableColumn v-for="column in [{p:'st_fee',l:'申通每单'}, {p:'st3',l:'申通拉均'}, {p:'st01',l:'申通超重'}, {p:'zt_fee',l:'中通每单'}, {p:'zt3',l:'中通拉均'}, {p:'zt01',l:'中通超重'}]" :key="column.p" :label="column.l" width="120"><template #default="{ row }"><ElInputNumber v-model="row[column.p]" :min="0" :controls="false" /></template></ElTableColumn><ElTableColumn label="新西1kg单价" width="135"><template #default="{ row }"><ElInputNumber v-model="row.xixi_1kg_unit_price" :min="0" :controls="false" placeholder="默认10" /></template></ElTableColumn><ElTableColumn label="特殊备注" min-width="190"><template #default="{ row }"><ElInput v-model="row.special_note" placeholder="仅备注，不参与计算" /></template></ElTableColumn><ElTableColumn label="操作" width="75" fixed="right" align="center"><template #default="{ $index }"><ElButton text type="danger" :icon="Delete" @click="removeCustomer($index)" /></template></ElTableColumn></ElTable>
          <div class="save-bar"><span v-if="customerDirty" class="dirty-tip">有未保存修改</span><ElButton type="primary" :loading="saving === 'customers'" @click="saveSection('customers')">保存客户配置</ElButton></div>
        </ElTabPane>
      </ElTabs>
    </section>
  </div>
</template>

<style scoped>
.config-icon{color:var(--ex-accent)}.config-card{padding:16px 22px 22px}.pane-intro{display:flex;align-items:center;justify-content:space-between;gap:18px;min-height:74px}.pane-intro h2{margin:0 0 5px;font-size:15px}.pane-intro p{margin:0;color:var(--ex-muted);font-size:12px}.save-bar{display:flex;align-items:center;justify-content:flex-end;gap:12px;padding-top:16px}.dirty-tip{color:var(--ex-warning);font-size:12px}.legacy-express :deep(.el-input-number){width:100%}.charge-list{display:grid;grid-template-columns:repeat(2,minmax(260px,380px));gap:14px}.charge-list>div{display:grid;grid-template-columns:80px 1fr 60px;align-items:center;gap:12px;padding:18px;border:1px solid var(--ex-border);border-radius:9px}.charge-list b{font-size:14px}.charge-list span{color:var(--ex-muted);font-size:12px}.runtime-grid{display:grid;grid-template-columns:360px minmax(340px,520px);gap:40px;padding:18px 4px}.runtime-info{padding:24px;border:1px solid var(--ex-border);border-radius:10px;background:#f8faff}.runtime-info span{display:block;margin-bottom:6px;color:var(--ex-muted);font-size:11px}.runtime-info strong{display:block;margin-bottom:22px;font:700 24px Consolas}.runtime-info p{margin:0;color:#667085;font-size:13px;line-height:1.8}.unit{margin-left:9px;color:var(--ex-muted);font-size:12px}
@media(max-width:850px){.pane-intro{align-items:flex-start;flex-direction:column;padding:14px 0}.runtime-grid,.charge-list{grid-template-columns:1fr}}
</style>
