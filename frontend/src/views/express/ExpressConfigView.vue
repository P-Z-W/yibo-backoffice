<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
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

const active = ref('customers')
const loading = ref(true)
const saving = ref(false)
const customers = ref<TeamPrice[]>([])
const carriers = ref<Array<{ name: string; identify_column: string; enabled: boolean }>>([])
const runtime = reactive({ extend_days_before: 15, extend_days_after: 5, process_month: '', sql_start_date: '', sql_end_date: '' })
const priceType = ref<'shentong' | 'zhongtong'>('shentong')
const prices = reactive<{ shentong: PriceRow[]; zhongtong: PriceRow[]; charge: Array<{ type: string; price: number }> }>({ shentong: [], zhongtong: [], charge: [] })

async function load() {
  loading.value = true
  try {
    const [customerData, carrierData, settingData, priceData] = await Promise.all([getTeamPrices(), getCarriers(), getExpressSettings(), getPriceBook()])
    customers.value = customerData
    carriers.value = carrierData.map(({ name, identify_column, enabled }) => ({ name, identify_column, enabled }))
    Object.assign(runtime, settingData)
    Object.assign(prices, priceData)
  } finally { loading.value = false }
}

function addCustomer() { customers.value.push({ team: '', st_fee: 0, st3: 0, st01: 0, zt_fee: 0, zt3: 0, zt01: 0, xixi_1kg_unit_price: null, special_note: '' }) }
async function removeCustomer(index: number) { await ElMessageBox.confirm('确定删除这条客户配置吗？', '删除确认', { type: 'warning' }); customers.value.splice(index, 1) }

async function saveCurrent() {
  saving.value = true
  try {
    if (active.value === 'customers') await saveTeamPrices(customers.value)
    if (active.value === 'carriers') await saveCarriers(carriers.value)
    if (active.value === 'runtime') await saveExpressSettings(runtime.extend_days_before, runtime.extend_days_after)
    if (active.value === 'prices') await savePriceBook(prices)
    ElMessage.success('配置已保存到新系统')
  } finally { saving.value = false }
}

onMounted(load)
</script>

<template>
  <div class="page-heading">
    <div><h1>快递对账配置</h1><p>报价、客户加收、快递识别和运行参数均已迁移到新数据库。</p></div>
    <ElButton type="primary" :loading="saving" @click="saveCurrent">保存当前配置</ElButton>
  </div>
  <section class="surface-card config-card" v-loading="loading">
    <ElTabs v-model="active">
      <ElTabPane label="客户情况" name="customers">
        <div class="tab-actions"><span>共 {{ customers.length }} 个客户</span><ElButton :icon="Plus" @click="addCustomer">新增客户</ElButton></div>
        <ElTable :data="customers" height="580" stripe>
          <ElTableColumn label="团队" min-width="170" fixed><template #default="{ row }"><ElInput v-model="row.team" /></template></ElTableColumn>
          <ElTableColumn label="申通每单" width="120"><template #default="{ row }"><ElInputNumber v-model="row.st_fee" :min="0" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="申通拉均" width="120"><template #default="{ row }"><ElInputNumber v-model="row.st3" :min="0" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="申通超重" width="120"><template #default="{ row }"><ElInputNumber v-model="row.st01" :min="0" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="中通每单" width="120"><template #default="{ row }"><ElInputNumber v-model="row.zt_fee" :min="0" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="中通拉均" width="120"><template #default="{ row }"><ElInputNumber v-model="row.zt3" :min="0" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="中通超重" width="120"><template #default="{ row }"><ElInputNumber v-model="row.zt01" :min="0" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="新西1kg单价" width="130"><template #default="{ row }"><ElInputNumber v-model="row.xixi_1kg_unit_price" :min="0" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="特殊备注" min-width="180"><template #default="{ row }"><ElInput v-model="row.special_note" /></template></ElTableColumn>
          <ElTableColumn width="60" fixed="right"><template #default="{ $index }"><ElButton text type="danger" :icon="Delete" @click="removeCustomer($index)" /></template></ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="快递识别" name="carriers">
        <div class="tab-actions"><span>根据原始账单表头自动识别快递公司</span><ElButton :icon="Plus" @click="carriers.push({ name:'', identify_column:'', enabled:true })">新增快递</ElButton></div>
        <ElTable :data="carriers" stripe>
          <ElTableColumn label="快递名称"><template #default="{ row }"><ElInput v-model="row.name" /></template></ElTableColumn>
          <ElTableColumn label="识别列"><template #default="{ row }"><ElInput v-model="row.identify_column" /></template></ElTableColumn>
          <ElTableColumn label="启用" width="110"><template #default="{ row }"><ElSwitch v-model="row.enabled" /></template></ElTableColumn>
          <ElTableColumn width="70"><template #default="{ $index }"><ElButton text type="danger" :icon="Delete" @click="carriers.splice($index,1)" /></template></ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="运行参数" name="runtime">
        <div class="runtime-grid">
          <ElForm label-position="top">
            <ElFormItem label="查询日期向前扩展"><ElInputNumber v-model="runtime.extend_days_before" :min="0" :max="60" /><span class="unit">天</span></ElFormItem>
            <ElFormItem label="查询日期向后扩展"><ElInputNumber v-model="runtime.extend_days_after" :min="0" :max="60" /><span class="unit">天</span></ElFormItem>
          </ElForm>
          <div class="runtime-info"><span>处理月份</span><strong>{{ runtime.process_month }}</strong><span>订单查询范围</span><p>{{ runtime.sql_start_date }}<br />至 {{ runtime.sql_end_date }}</p></div>
        </div>
      </ElTabPane>

      <ElTabPane label="报价表" name="prices">
        <div class="tab-actions"><ElRadioGroup v-model="priceType"><ElRadioButton value="shentong">申通报价</ElRadioButton><ElRadioButton value="zhongtong">中通报价</ElRadioButton></ElRadioGroup><div class="charge-row"><span v-for="item in prices.charge" :key="item.type">{{ item.type }}充单价 <ElInputNumber v-model="item.price" :min="0" :controls="false" /></span></div></div>
        <ElTable :data="prices[priceType]" height="560" stripe>
          <ElTableColumn label="省份" min-width="150"><template #default="{ row }"><ElInput v-model="row.province" /></template></ElTableColumn>
          <ElTableColumn label="3kg内面单费"><template #default="{ row }"><ElInputNumber v-model="row.fee_3kg" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="超3kg面单费"><template #default="{ row }"><ElInputNumber v-model="row.fee_over3kg" :controls="false" /></template></ElTableColumn>
          <ElTableColumn label="续重单价"><template #default="{ row }"><ElInputNumber v-model="row.unit_price" :controls="false" /></template></ElTableColumn>
        </ElTable>
      </ElTabPane>
    </ElTabs>
  </section>
</template>

<style scoped>
.config-card { padding:18px 24px 25px; }
.tab-actions { display:flex; align-items:center; justify-content:space-between; min-height:52px; color:#8c97a8; font-size:12px; }
.config-card :deep(.el-input-number) { width:100%; }
.runtime-grid { display:grid; grid-template-columns:360px 1fr; gap:40px; padding:28px 8px; }
.runtime-info { max-width:480px; padding:28px; border:1px solid #e8ecf2; border-radius:12px; background:#f8faff; }
.runtime-info span { display:block; margin-bottom:7px; color:#8d98a9; font-size:11px; }
.runtime-info strong { display:block; margin-bottom:25px; color:#24334c; font-size:25px; }
.runtime-info p { color:#506079; line-height:1.8; }
.unit { margin-left:10px; color:#8d98aa; }
.charge-row { display:flex; gap:25px; }
.charge-row span { display:flex; align-items:center; gap:8px; color:#59677d; }
.charge-row :deep(.el-input-number) { width:100px; }
</style>
