<script setup lang="ts">
import { Delete, Download, Plus, VideoPlay } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  addQuery,
  deleteQuery,
  getQueryWorkspace,
  runQueries,
  saveQuery,
  type QueryEntry,
  type QueryHistory,
} from '../api/queryExport'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(true)
const groups = ref<Record<string, QueryEntry[]>>({})
const history = ref<QueryHistory[]>([])
const activeGroup = ref('')
const active = ref<QueryEntry>()
const selectedIds = ref<number[]>([])
const logs = ref<string[]>([])
const running = ref(false)
let source: EventSource | null = null

const groupEntries = computed(() => groups.value[activeGroup.value] ?? [])

async function load() {
  loading.value = true
  try {
    const data = await getQueryWorkspace()
    groups.value = data.groups
    history.value = data.history
    running.value = data.job.running
    if (!activeGroup.value) activeGroup.value = Object.keys(groups.value)[0] ?? ''
    if (!active.value) active.value = groupEntries.value[0]
  } finally { loading.value = false }
}

function choose(entry: QueryEntry) { active.value = entry; activeGroup.value = entry.group_name }

async function add() {
  if (!activeGroup.value) return
  const entry = await addQuery(activeGroup.value)
  groups.value[activeGroup.value].unshift(entry)
  active.value = entry
}

async function remove(entry: QueryEntry) {
  await ElMessageBox.confirm(`确定删除“${entry.filename || '未命名查询'}”吗？`, '删除查询', { type: 'warning' })
  await deleteQuery(entry.id)
  groups.value[entry.group_name] = groups.value[entry.group_name].filter((item) => item.id !== entry.id)
  if (active.value?.id === entry.id) active.value = groups.value[entry.group_name][0]
}

async function save() {
  if (!active.value) return
  active.value = await saveQuery(active.value)
  ElMessage.success('查询配置已保存')
}

async function run() {
  if (!selectedIds.value.length) return ElMessage.warning('请勾选要导出的查询')
  await runQueries(selectedIds.value)
  logs.value = []
  running.value = true
  source?.close()
  source = new EventSource('/api/v1/query-export/logs')
  source.onmessage = async (event) => {
    const message = JSON.parse(event.data) as string
    if (message === '__DONE__') { running.value = false; source?.close(); await load() }
    else if (message !== '__PING__') logs.value.push(message)
  }
}

onMounted(load)
onBeforeUnmount(() => source?.close())
</script>

<template>
  <div class="page-heading">
    <div><h1>查询导出</h1><p>4 条历史查询配置已迁移，SQL 只允许执行只读 SELECT / WITH。</p></div>
    <ElButton v-if="auth.can('query.run')" type="primary" :icon="VideoPlay" :loading="running" @click="run">运行所选查询</ElButton>
  </div>

  <div class="query-layout" v-loading="loading">
    <aside class="surface-card query-list">
      <div class="list-heading"><strong>查询列表</strong><ElButton v-if="auth.can('query.configure')" text type="primary" :icon="Plus" @click="add">新增</ElButton></div>
      <ElTabs v-model="activeGroup" stretch>
        <ElTabPane v-for="(_, group) in groups" :key="group" :name="group" :label="group" />
      </ElTabs>
      <ElCheckboxGroup v-model="selectedIds" class="entries">
        <div v-for="entry in groupEntries" :key="entry.id" :class="['entry', { active: active?.id === entry.id }]" @click="choose(entry)">
          <ElCheckbox :value="entry.id" :disabled="!auth.can('query.run')" @click.stop />
          <div><strong>{{ entry.filename || '未命名查询' }}</strong><span>{{ entry.sql_preview || '尚未填写 SQL' }}</span></div>
          <ElButton v-if="auth.can('query.configure')" text type="danger" :icon="Delete" @click.stop="remove(entry)" />
        </div>
      </ElCheckboxGroup>
    </aside>

    <main class="surface-card editor-card">
      <template v-if="active">
        <div class="editor-heading"><div><span>输出文件名</span><ElInput v-model="active.filename" :disabled="!auth.can('query.configure')" placeholder="请输入导出文件名" /></div><ElButton v-if="auth.can('query.configure')" type="primary" @click="save">保存查询</ElButton></div>
        <label>SQL 语句</label>
        <ElInput v-model="active.sql_content" :disabled="!auth.can('query.configure')" type="textarea" :rows="21" resize="none" class="sql-editor" spellcheck="false" />
      </template>
      <ElEmpty v-else description="请选择一条查询" />
    </main>
  </div>

  <div class="bottom-grid">
    <section class="surface-card log-card"><div class="section-heading"><h3>运行日志</h3><span>{{ running ? '运行中' : '空闲' }}</span></div><pre>{{ logs.length ? logs.join('\n') : '选择查询并运行后，日志将在这里显示。' }}</pre></section>
    <section class="surface-card history-card"><div class="section-heading"><h3>历史导出</h3><span>{{ history.length }} 个日期</span></div><div class="history-list"><div v-for="record in history" :key="record.date"><strong>{{ record.date }}</strong><template v-for="file in record.files" :key="file"><a v-if="auth.can('query.download')" :href="`/api/v1/query-export/download/${record.date}/${encodeURIComponent(file)}`"><Download />{{ file }}</a><span v-else>{{ file }}</span></template></div></div></section>
  </div>
</template>

<style scoped>
.query-layout { display:grid; grid-template-columns:360px 1fr; gap:18px; margin-bottom:18px; }
.query-list,.editor-card,.log-card,.history-card { padding:20px 22px; }
.list-heading,.editor-heading,.section-heading { display:flex; align-items:center; justify-content:space-between; gap:15px; }
.list-heading strong,.section-heading h3 { color:#243149; font-size:15px; }
.entries { max-height:610px; overflow:auto; }
.entry { display:grid; grid-template-columns:24px 1fr 30px; align-items:center; gap:8px; padding:12px 8px; border-bottom:1px solid #edf0f4; cursor:pointer; }
.entry.active { border-radius:8px; border-bottom-color:transparent; background:#edf4ff; }
.entry div { min-width:0; }
.entry strong,.entry span { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.entry strong { color:#334159; font-size:12px; }.entry span { margin-top:5px; color:#929dad; font-size:10px; }
.editor-heading { margin-bottom:18px; }.editor-heading>div { display:flex; width:70%; align-items:center; gap:12px; }.editor-heading span,label { flex:0 0 auto; color:#68768c; font-size:12px; }
label { display:block; margin-bottom:9px; }.sql-editor :deep(textarea) { color:#c9d8ec; background:#0e1e37; font:12px/1.75 'Consolas',monospace; }
.bottom-grid { display:grid; grid-template-columns:1fr 1fr; gap:18px; }.section-heading span { color:#97a1b1; font-size:10px; }
.log-card pre { height:230px; padding:16px; overflow:auto; border-radius:9px; color:#b8d4f3; background:#0d1d36; font:11px/1.7 'Consolas',monospace; white-space:pre-wrap; }
.history-list { height:230px; margin-top:12px; overflow:auto; }.history-list>div { padding:10px 0; border-bottom:1px solid #edf0f4; }.history-list strong { display:block; margin-bottom:7px; color:#47546a; font-size:11px; }.history-list a { display:flex; align-items:center; gap:5px; margin-top:5px; color:#2f6feb; font-size:10px; text-decoration:none; }.history-list svg { width:13px; }
@media(max-width:1000px){.query-layout{grid-template-columns:1fr}.bottom-grid{grid-template-columns:1fr}}
</style>
