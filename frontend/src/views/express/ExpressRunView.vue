<script setup lang="ts">
import { UploadFilled, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadFiles } from 'element-plus'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { getExpressJob, getExpressOverview, startExpressRun, uploadExpressFile } from '../../api/express'

const processMonth = ref('')
const files = ref<File[]>([])
const uploading = ref(false)
const running = ref(false)
const activeStep = ref(0)
const logs = ref<string[]>([])
let source: EventSource | null = null
let timer: number | null = null

function onFiles(_file: UploadFile, list: UploadFiles) {
  files.value = list.flatMap((item) => (item.raw ? [item.raw] : []))
}

async function uploadAll() {
  if (!files.value.length) return ElMessage.warning('请先选择账单文件')
  uploading.value = true
  try {
    for (const file of files.value) await uploadExpressFile(processMonth.value, file)
    ElMessage.success(`已上传 ${files.value.length} 个文件`)
  } finally { uploading.value = false }
}

function connectLogs() {
  source?.close()
  source = new EventSource('/api/v1/express/logs')
  source.onmessage = (event) => {
    const message = JSON.parse(event.data) as string
    if (message.startsWith('__STEP__')) activeStep.value = Number(message.replace('__STEP__', ''))
    else if (message === '__DONE__') { running.value = false; source?.close() }
    else if (message !== '__PING__') logs.value.push(message)
  }
}

async function run() {
  try {
    await startExpressRun()
    logs.value = []
    activeStep.value = 0
    running.value = true
    connectLogs()
  } catch { ElMessage.error('任务未能启动，请检查账单文件或当前运行状态') }
}

async function refreshStatus() {
  const state = await getExpressJob()
  running.value = state.running
}

onMounted(async () => {
  processMonth.value = (await getExpressOverview()).process_month
  await refreshStatus()
  timer = window.setInterval(refreshStatus, 5000)
})

onBeforeUnmount(() => { source?.close(); if (timer) window.clearInterval(timer) })
</script>

<template>
  <div class="page-heading">
    <div><h1>运行快递对账</h1><p>上传 {{ processMonth }} 原始账单，执行订单下载、账单合并、运单匹配和客户拆分。</p></div>
    <ElTag :type="running ? 'warning' : 'success'" effect="light" round>{{ running ? '运行中' : '当前空闲' }}</ElTag>
  </div>

  <div class="run-grid">
    <section class="surface-card upload-card">
      <div class="section-title"><h3>1. 上传账单</h3><span>{{ processMonth }}</span></div>
      <ElUpload drag multiple :auto-upload="false" accept=".xlsx,.xls" :on-change="onFiles" :on-remove="onFiles">
        <ElIcon class="el-icon--upload"><UploadFilled /></ElIcon>
        <div class="el-upload__text">拖入申通 / 中通账单，或<em>点击选择</em></div>
        <template #tip><span>文件只保存到新系统，不会写入老系统目录。</span></template>
      </ElUpload>
      <ElButton type="primary" plain :loading="uploading" :disabled="!files.length" class="full-button" @click="uploadAll">上传所选文件</ElButton>
    </section>

    <section class="surface-card process-card">
      <div class="section-title"><h3>2. 执行流程</h3><span>成熟业务引擎</span></div>
      <ElSteps direction="vertical" :active="activeStep" finish-status="success" process-status="process">
        <ElStep title="下载订单数据" description="只读连接订单数据库" />
        <ElStep title="清洗合并账单" description="自动识别快递账单格式" />
        <ElStep title="运单匹配计费" description="匹配团队并按成熟规则计费" />
        <ElStep title="拆分客户账单" description="生成客户账单与汇总" />
      </ElSteps>
      <ElButton type="primary" :icon="VideoPlay" :loading="running" class="full-button" @click="run">开始运行</ElButton>
    </section>
  </div>

  <section class="surface-card log-card">
    <div class="section-title"><h3>实时日志</h3><span>{{ logs.length }} 条</span></div>
    <pre>{{ logs.length ? logs.join('\n') : '任务日志将在这里实时显示。' }}</pre>
  </section>
</template>

<style scoped>
.run-grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px; }
.upload-card,.process-card,.log-card { padding:24px 26px; }
.section-title { display:flex; align-items:center; justify-content:space-between; margin-bottom:20px; }
.section-title h3 { margin:0; color:#243149; font-size:16px; }
.section-title span { color:#929dad; font-size:11px; }
.full-button { width:100%; margin-top:20px; }
.process-card :deep(.el-steps) { height:250px; padding-left:12px; }
.log-card pre { min-height:230px; max-height:380px; margin:0; padding:20px; overflow:auto; border-radius:10px; color:#b8d4f3; background:#0d1d36; font:12px/1.8 'Consolas',monospace; white-space:pre-wrap; }
@media(max-width:900px){.run-grid{grid-template-columns:1fr}}
</style>
