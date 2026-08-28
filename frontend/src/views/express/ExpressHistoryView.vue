<script setup lang="ts">
import { Download } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getExpressHistory, type ExpressHistory } from '../../api/express'
import { useAuthStore } from '../../stores/auth'

const loading = ref(false)
const records = ref<ExpressHistory[]>([])
const router = useRouter()
const auth = useAuthStore()

async function load() {
  loading.value = true
  try { records.value = await getExpressHistory() } finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="legacy-express">
    <h1 class="legacy-page-title"><span class="history-icon">◷</span>历史处理记录</h1>
    <section class="legacy-card history-card" v-loading="loading">
      <ElTable :data="records" stripe>
        <ElTableColumn prop="month" label="处理月份" min-width="125" />
        <ElTableColumn label="最后结果" width="120"><template #default="{ row }"><ElTag :type="row.last_result === '成功' ? 'success' : row.last_result === '失败' ? 'danger' : 'info'" effect="light">{{ row.last_result }}</ElTag></template></ElTableColumn>
        <ElTableColumn prop="run_count" label="运行次数" width="110" />
        <ElTableColumn prop="last_time" label="最后运行时间" min-width="175"><template #default="{ row }">{{ row.last_time || '—' }}</template></ElTableColumn>
        <ElTableColumn prop="last_duration" label="耗时" width="110"><template #default="{ row }">{{ row.last_duration || '—' }}</template></ElTableColumn>
        <ElTableColumn label="操作" width="230" align="right">
          <template #default="{ row }">
            <ElButton v-if="auth.can('express.download')" plain type="success" size="small" :icon="Download" tag="a" :href="`/api/v1/express/download/${row.month}`">下载结果</ElButton>
            <ElButton plain type="primary" size="small" @click="router.push(`/express/stats?month=${row.month}`)">查看统计</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>
  </div>
</template>

<style scoped>
.history-icon{color:var(--ex-accent)}
.history-card{padding:18px}
</style>
