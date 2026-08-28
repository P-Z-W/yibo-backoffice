<script setup lang="ts">
import { Document, VideoPlay } from '@element-plus/icons-vue'
import { isAxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  getExpressJob,
  getExpressOverview,
  startExpressRun,
  uploadExpressFile,
  type ExpressJob,
} from '../../api/express'

type UploadSlot = {
  carrier: string
  filename: string
  uploaded: boolean
  uploading: boolean
  message: string
  error: boolean
}

const processMonth = ref('')
const state = reactive<ExpressJob>({
  running: false,
  success: false,
  period: '',
  elapsed: '',
  message: '',
  step: 0,
  progress: 0,
})
const slots = reactive<UploadSlot[]>([
  { carrier: '申通账单', filename: '', uploaded: false, uploading: false, message: '', error: false },
  { carrier: '中通账单', filename: '', uploaded: false, uploading: false, message: '', error: false },
])
let source: EventSource | null = null
let timer: number | null = null

const statusText = computed(() => {
  if (state.running) return state.message || '对账任务运行中...'
  if (state.success) return state.message || '运行完成'
  if (state.message && state.message !== '任务启动') return state.message
  return '等待开始'
})

function errorText(error: unknown) {
  if (isAxiosError(error)) return String(error.response?.data?.detail || error.message)
  return error instanceof Error ? error.message : '操作失败'
}

async function chooseFile(index: number, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const slot = slots[index]
  slot.filename = file.name
  slot.uploading = true
  slot.uploaded = false
  slot.error = false
  slot.message = '上传中...'
  try {
    await uploadExpressFile(processMonth.value, file)
    slot.uploaded = true
    slot.message = '上传成功'
  } catch (error) {
    slot.error = true
    slot.message = errorText(error)
  } finally {
    slot.uploading = false
  }
}

function connectLogs() {
  source?.close()
  source = new EventSource('/api/v1/express/logs')
  source.onmessage = async (event) => {
    const message = JSON.parse(event.data) as string
    if (message === '__DONE__') {
      source?.close()
      source = null
      await refreshStatus()
      if (state.success) ElMessage.success('快递对账运行完成')
    } else if (message !== '__PING__') {
      await refreshStatus()
    }
  }
  source.onerror = () => {
    source?.close()
    source = null
  }
}

async function run() {
  try {
    await startExpressRun()
    Object.assign(state, { running: true, success: false, step: 0, progress: 5, message: '任务启动' })
    connectLogs()
  } catch (error) {
    ElMessage.error(errorText(error))
  }
}

async function refreshStatus() {
  try {
    Object.assign(state, await getExpressJob())
    if (state.running && !source) connectLogs()
  } catch {
    // 定时刷新失败不打断当前页面操作。
  }
}

onMounted(async () => {
  processMonth.value = (await getExpressOverview()).process_month
  await refreshStatus()
  timer = window.setInterval(refreshStatus, 3000)
})

onBeforeUnmount(() => {
  source?.close()
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div class="legacy-express">
    <h1 class="legacy-page-title">
      <span class="title-icon">▶</span>运行操作
      <span class="sub">上传账单并执行对账流程</span>
    </h1>

    <div class="run-grid">
      <section class="legacy-card upload-card">
        <h2 class="legacy-card-title">账单上传 &amp; 运行</h2>
        <div v-for="(slot, index) in slots" :key="slot.carrier" class="upload-item">
          <div class="upload-label">
            <span class="upload-dot" :class="{ done: slot.uploaded }" />
            {{ slot.carrier }}
          </div>
          <label class="upload-box" :class="{ uploaded: slot.uploaded }">
            <span class="upload-filename" :class="{ placeholder: !slot.filename }">
              {{ slot.filename || `点击选择${slot.carrier}（.xlsx）` }}
            </span>
            <ElIcon class="upload-file-icon"><Document /></ElIcon>
            <input type="file" accept=".xlsx" :disabled="slot.uploading || state.running" @change="chooseFile(index, $event)" />
          </label>
          <div v-if="slot.message" class="upload-msg" :class="slot.error ? 'err' : 'ok'">
            {{ slot.message }}
          </div>
        </div>

        <ElButton class="run-btn" type="primary" :icon="VideoPlay" :loading="state.running" @click="run">
          {{ state.running ? '正在运行...' : '开始运行' }}
        </ElButton>
        <a v-if="state.success && state.period" class="download-btn" :href="`/api/v1/express/download/${state.period}`">
          下载本次结果 ZIP
        </a>
      </section>

      <section class="legacy-card process-card">
        <h2 class="legacy-card-title">运行进度</h2>
        <div class="log-status">
          <span class="status-dot" :class="{ running: state.running, done: !state.running && state.success, error: !state.running && !state.success && !!state.message }" />
          <span class="status-text">{{ statusText }}</span>
        </div>
        <div class="progress-wrap">
          <ElProgress :percentage="state.progress || 0" :status="state.success ? 'success' : undefined" :stroke-width="6" />
        </div>
        <div class="steps-wrap">
          <div v-for="(step, index) in ['下载订单数据', '清洗合并账单', '运单匹配计费', '拆分客户账单']" :key="step" class="step-item" :class="{ active: state.running && state.step === index, done: state.step > index || state.success }">
            <span class="step-index">{{ index + 1 }}</span>
            <div><strong>{{ step }}</strong><small>{{ ['只读连接订单数据库', '自动识别申通与中通账单', '匹配团队并按成熟规则计费', '生成客户账单与汇总'][index] }}</small></div>
          </div>
        </div>
        <div class="elapsed">运行耗时：<strong>{{ state.elapsed || '—' }}</strong></div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.title-icon { color:var(--ex-accent); font-size:14px; }
.run-grid { display:grid; grid-template-columns:360px 1fr; gap:20px; }
.upload-card,.process-card { padding:22px 20px; }
.upload-item { margin-bottom:16px; }
.upload-label { display:flex; align-items:center; gap:7px; margin-bottom:8px; color:var(--ex-muted); font-size:12px; }
.upload-dot { width:6px; height:6px; border-radius:50%; background:var(--ex-border); }
.upload-dot.done { background:var(--ex-success); }
.upload-box { position:relative; display:flex; align-items:center; justify-content:space-between; min-height:50px; padding:14px 16px; overflow:hidden; border:1.5px dashed var(--ex-border); border-radius:8px; cursor:pointer; transition:.2s; }
.upload-box:hover { border-color:var(--ex-accent); background:#f8faff; }
.upload-box.uploaded { border-color:var(--ex-success); border-style:solid; }
.upload-box input { position:absolute; inset:0; width:100%; height:100%; opacity:0; cursor:pointer; }
.upload-filename { max-width:260px; overflow:hidden; color:var(--ex-text); font:12px Consolas,monospace; text-overflow:ellipsis; white-space:nowrap; }
.upload-filename.placeholder,.upload-file-icon { color:var(--ex-muted); }
.upload-msg { margin-top:6px; padding:6px 10px; border-radius:6px; font:12px Consolas,monospace; }
.upload-msg.ok { color:var(--ex-success); background:#ecfdf3; }
.upload-msg.err { color:var(--ex-danger); background:#fef2f2; }
.run-btn { width:100%; margin-top:4px; }
.download-btn { display:block; margin-top:10px; padding:10px; border:1px solid var(--ex-success); border-radius:8px; color:var(--ex-success); font-size:13px; text-align:center; text-decoration:none; }
.log-status { display:flex; align-items:center; gap:8px; margin-bottom:16px; }
.status-dot { width:8px; height:8px; border-radius:50%; background:var(--ex-border); }
.status-dot.running { background:var(--ex-accent); animation:pulse 1.2s infinite; }
.status-dot.done { background:var(--ex-success); }
.status-dot.error { background:var(--ex-danger); }
.status-text { color:var(--ex-muted); font:12px Consolas,monospace; }
.progress-wrap { margin-bottom:22px; }
.steps-wrap { position:relative; padding-left:32px; }
.steps-wrap::before { position:absolute; top:16px; bottom:16px; left:9px; width:1px; background:var(--ex-border); content:''; }
.step-item { position:relative; display:flex; align-items:center; gap:12px; min-height:57px; margin-bottom:6px; padding:10px 14px; border:1px solid transparent; border-radius:8px; color:var(--ex-muted); }
.step-item::before { position:absolute; top:50%; left:-29px; z-index:1; width:14px; height:14px; border:2px solid var(--ex-border); border-radius:50%; background:#f3f6fb; content:''; transform:translateY(-50%); }
.step-item.active { border-color:#bfdbfe; color:var(--ex-accent); background:#eff6ff; }
.step-item.active::before { border-color:var(--ex-accent); background:var(--ex-accent); box-shadow:0 0 0 4px #dbeafe; }
.step-item.done { color:var(--ex-success); }
.step-item.done::before { border-color:var(--ex-success); background:var(--ex-success); }
.step-index { width:20px; color:inherit; font:600 12px Consolas,monospace; }
.step-item strong { display:block; font-size:13px; }
.step-item small { display:block; margin-top:4px; color:var(--ex-muted); font-size:11px; }
.elapsed { margin-top:18px; padding-top:15px; border-top:1px solid var(--ex-border); color:var(--ex-muted); font-size:12px; text-align:right; }
.elapsed strong { color:var(--ex-text); font-family:Consolas,monospace; }
@keyframes pulse { 50% { opacity:.45; transform:scale(.8); } }
@media(max-width:900px){.run-grid{grid-template-columns:1fr}}
</style>
