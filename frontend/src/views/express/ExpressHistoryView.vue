<script setup lang="ts">
import { Download, Refresh } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getExpressHistory, type ExpressHistory } from '../../api/express'
import { formatCount } from '../../utils/format'

const loading = ref(false)
const records = ref<ExpressHistory[]>([])
const router = useRouter()

async function load() {
  loading.value = true
  try { records.value = await getExpressHistory() } finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <div class="page-heading">
    <div><h1>历史归档</h1><p>旧系统全部月份的运行记录和结果文件已经迁移。</p></div>
    <ElButton :icon="Refresh" @click="load">刷新</ElButton>
  </div>
  <section class="surface-card history-card" v-loading="loading">
    <ElTable :data="records" stripe>
      <ElTableColumn prop="month" label="月份" min-width="120" />
      <ElTableColumn prop="run_count" label="运行次数" width="110" />
      <ElTableColumn label="最后结果" width="120">
        <template #default="{ row }"><ElTag :type="row.last_result === '成功' ? 'success' : 'info'" effect="light">{{ row.last_result }}</ElTag></template>
      </ElTableColumn>
      <ElTableColumn prop="last_duration" label="耗时" width="120" />
      <ElTableColumn label="文件" width="120"><template #default="{ row }">{{ row.file_count }} 个</template></ElTableColumn>
      <ElTableColumn label="大小" width="120"><template #default="{ row }">{{ formatCount(Math.round(row.size_bytes / 1024 / 1024)) }} MB</template></ElTableColumn>
      <ElTableColumn label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <ElButton text type="primary" @click="router.push(`/express/stats?month=${row.month}`)">查看统计</ElButton>
          <ElButton text type="primary" :icon="Download" tag="a" :href="`/api/v1/express/download/${row.month}`">下载</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>
  </section>
</template>

<style scoped>
.history-card { padding:18px; }
</style>
