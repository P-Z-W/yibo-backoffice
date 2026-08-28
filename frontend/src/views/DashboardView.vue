<script setup lang="ts">
import {
  Box,
  CircleCheck,
  DataAnalysis,
  Document,
  Files,
  Lock,
  Operation,
  Right,
  Search,
  Setting,
  UserFilled,
  Wallet,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { http } from '../api/http'
import { useAuthStore } from '../stores/auth'

interface SystemOverview {
  version: string
  database: string
  modules: Array<{ name: string; status: 'ready' }>
  analytics: {
    metric_definitions: number
    metric_values: number
    monthly_reviews: number
  }
}

interface ModuleCard {
  key: string
  title: string
  description: string
  action: string
  path: string
  badge: string
  tone: string
  icon: Component
}

const router = useRouter()
const auth = useAuthStore()
const systemOverview = ref<SystemOverview>()
const systemLoading = ref(false)
const systemLoadFailed = ref(false)

const roleCodes = computed(() => auth.user?.roles ?? (auth.user?.role ? [auth.user.role] : []))
const roleNames = computed(() => {
  if (auth.user?.role_names?.length) return auth.user.role_names
  return auth.user?.role_name ? [auth.user.role_name] : []
})

function hasRole(code: string) {
  return roleCodes.value.includes(code)
}

const profile = computed(() => {
  if (auth.isSystemAdmin) {
    return {
      eyebrow: '系统管理员',
      title: '系统管理工作台',
      description: '管理系统运行、账号权限与全部业务模块。',
    }
  }
  if (hasRole('management')) {
    return {
      eyebrow: '经营管理',
      title: '经营管理工作台',
      description: '聚焦经营指标、月度复盘和全局业务数据。',
    }
  }
  if (hasRole('supervisor')) {
    return {
      eyebrow: '仓库主管',
      title: '主管工作台',
      description: '处理团队业务、对账任务和本组报销审批。',
    }
  }
  if (hasRole('team_leader')) {
    return {
      eyebrow: '组长',
      title: '组长工作台',
      description: '查看本组报销进度并处理组内审批事项。',
    }
  }
  if (hasRole('finance')) {
    return {
      eyebrow: '财务人员',
      title: '财务工作台',
      description: '处理工资、报销审批、财务导出与相关数据。',
    }
  }
  if (hasRole('operator')) {
    return {
      eyebrow: '运营对账',
      title: '运营工作台',
      description: '快速进入快递对账、查询导出和日常运营任务。',
    }
  }
  if (hasRole('employee')) {
    return {
      eyebrow: '普通员工',
      title: '我的工作台',
      description: '查看和填报与自己相关的日常业务。',
    }
  }
  return {
    eyebrow: roleNames.value.join('、') || '已登录',
    title: '专属工作台',
    description: '工作内容已根据你当前的角色权限自动配置。',
  }
})

const moduleCards = computed<ModuleCard[]>(() => {
  const cards: ModuleCard[] = []

  if (auth.can('analytics.view')) {
    cards.push({
      key: 'analytics',
      title: '经营分析',
      description: auth.can('analytics.manage')
        ? '查看经营指标并维护月度复盘。'
        : '查看经营指标、趋势和月度复盘。',
      action: '进入经营分析',
      path: '/analytics',
      badge: auth.can('analytics.manage') ? '可维护' : '查看',
      tone: 'blue',
      icon: DataAnalysis,
    })
  }

  if (auth.can('express.view') || auth.can('express.run') || auth.can('express.configure')) {
    const path = auth.can('express.run')
      ? '/express/run'
      : auth.can('express.view')
        ? '/express'
        : '/express/config'
    cards.push({
      key: 'express',
      title: '快递对账',
      description: auth.can('express.run')
        ? '运行对账任务，查看处理历史和统计结果。'
        : '查看快递对账结果、历史和统计数据。',
      action: auth.can('express.run') ? '开始对账' : '查看对账',
      path,
      badge: auth.can('express.configure')
        ? '可配置'
        : auth.can('express.run')
          ? '可运行'
          : '查看',
      tone: 'cyan',
      icon: Operation,
    })
  }

  if (auth.can('query.view')) {
    cards.push({
      key: 'query',
      title: '数据查询',
      description: auth.can('query.configure')
        ? '执行查询导出并维护查询配置。'
        : '按已有配置查询和导出业务数据。',
      action: '进入数据查询',
      path: '/query',
      badge: auth.can('query.configure') ? '可配置' : auth.can('query.run') ? '可执行' : '查看',
      tone: 'purple',
      icon: Search,
    })
  }

  if (auth.can('salary.view')) {
    cards.push({
      key: 'salary',
      title: '员工工资',
      description: auth.can('salary.manage')
        ? '维护工资记录并完成工资数据导出。'
        : '查看授权范围内的员工工资数据。',
      action: '进入工资管理',
      path: '/salary',
      badge: auth.can('salary.manage') ? '可维护' : '查看',
      tone: 'orange',
      icon: Wallet,
    })
  }

  if (auth.can('reimbursement.view')) {
    const canApprove =
      auth.can('reimbursement.approve_supervisor') || auth.can('reimbursement.approve_finance')
    cards.push({
      key: 'reimbursement',
      title: '报销管理',
      description: canApprove
        ? '查看报销进度并处理权限范围内的审批。'
        : '新建报销单并跟进自己的报销进度。',
      action: canApprove ? '处理报销' : '查看我的报销',
      path: '/reimbursement',
      badge: canApprove ? '可审批' : auth.can('reimbursement.create') ? '可填报' : '查看',
      tone: 'green',
      icon: Document,
    })
  }

  if (auth.can('storage.view')) {
    cards.push({
      key: 'storage',
      title: '仓储费',
      description: '查看仓储费用模块和后续业务能力。',
      action: '进入仓储费',
      path: '/storage',
      badge: '查看',
      tone: 'slate',
      icon: Box,
    })
  }

  if (auth.isSystemAdmin) {
    cards.push({
      key: 'access',
      title: '账号与权限',
      description: '管理员工账号、岗位角色、权限和操作日志。',
      action: '进入系统管理',
      path: '/access',
      badge: '仅管理员',
      tone: 'red',
      icon: Lock,
    })
  }

  return cards
})

const primaryAction = computed(() => {
  if (auth.isSystemAdmin) return { label: '管理账号与权限', path: '/access', icon: Setting }
  if (hasRole('management') && auth.can('analytics.view')) {
    return { label: '查看经营分析', path: '/analytics', icon: DataAnalysis }
  }
  if (
    (hasRole('supervisor') || hasRole('team_leader') || hasRole('finance')) &&
    auth.can('reimbursement.view')
  ) {
    return { label: '处理报销事项', path: '/reimbursement', icon: Document }
  }
  if (hasRole('operator') && auth.can('express.run')) {
    return { label: '开始快递对账', path: '/express/run', icon: Operation }
  }
  if (auth.can('reimbursement.view')) {
    return { label: '查看我的报销', path: '/reimbursement', icon: Document }
  }
  const first = moduleCards.value[0]
  return first ? { label: first.action, path: first.path, icon: first.icon } : null
})

async function loadSystemOverview() {
  if (!auth.isSystemAdmin) return
  systemLoading.value = true
  systemLoadFailed.value = false
  try {
    const { data } = await http.get<SystemOverview>('/system/overview')
    systemOverview.value = data
  } catch {
    systemLoadFailed.value = true
  } finally {
    systemLoading.value = false
  }
}

onMounted(loadSystemOverview)
</script>

<template>
  <div class="dashboard-page">
    <section class="workspace-hero">
      <div class="hero-copy">
        <span class="hero-eyebrow">{{ profile.eyebrow }}</span>
        <h1>{{ profile.title }}</h1>
        <p>{{ auth.user?.display_name }}，{{ profile.description }}</p>
        <div class="identity-tags">
          <ElTag v-for="name in roleNames" :key="name" effect="plain" round>{{ name }}</ElTag>
          <ElTag v-if="auth.user?.team" type="info" effect="plain" round>{{ auth.user.team }}</ElTag>
        </div>
      </div>
      <div class="hero-action">
        <div class="hero-symbol"><UserFilled /></div>
        <ElButton
          v-if="primaryAction"
          type="primary"
          size="large"
          :icon="primaryAction.icon"
          @click="router.push(primaryAction.path)"
        >
          {{ primaryAction.label }}
        </ElButton>
      </div>
    </section>

    <section class="module-section">
      <div class="section-heading">
        <div>
          <h2>我的工作入口</h2>
          <p>这里只显示当前账号有权使用的业务模块。</p>
        </div>
        <span>{{ moduleCards.length }} 个可用模块</span>
      </div>

      <div class="module-grid">
        <button
          v-for="item in moduleCards"
          :key="item.key"
          type="button"
          class="surface-card module-card"
          @click="router.push(item.path)"
        >
          <span :class="['module-icon', item.tone]"><component :is="item.icon" /></span>
          <span class="module-copy">
            <span class="module-title">
              <strong>{{ item.title }}</strong>
              <ElTag size="small" effect="plain">{{ item.badge }}</ElTag>
            </span>
            <span>{{ item.description }}</span>
            <small>{{ item.action }} <Right /></small>
          </span>
        </button>
      </div>
    </section>

    <section v-if="auth.isSystemAdmin" class="admin-section">
      <div class="section-heading admin-heading">
        <div>
          <h2>系统信息</h2>
          <p>数据库、版本和迁移状态仅系统管理员可见。</p>
        </div>
        <ElTag type="danger" effect="plain" round><Lock /> 仅系统管理员</ElTag>
      </div>

      <ElAlert
        v-if="systemLoadFailed"
        title="暂时无法读取系统信息，请确认后端服务已启动。"
        type="warning"
        :closable="false"
        show-icon
      />

      <div v-loading="systemLoading" class="system-panel">
        <div class="system-stats">
          <article class="surface-card system-stat">
            <span>数据库</span>
            <strong>{{ systemOverview?.database ?? '—' }}</strong>
            <small>独立业务数据库</small>
          </article>
          <article class="surface-card system-stat">
            <span>系统版本</span>
            <strong>{{ systemOverview?.version ?? '—' }}</strong>
            <small>当前运行版本</small>
          </article>
          <article class="surface-card system-stat">
            <span>指标定义</span>
            <strong>{{ systemOverview?.analytics.metric_definitions ?? '—' }}</strong>
            <small>{{ systemOverview?.analytics.metric_values ?? '—' }} 条指标数据</small>
          </article>
          <article class="surface-card system-stat">
            <span>月度复盘</span>
            <strong>{{ systemOverview?.analytics.monthly_reviews ?? '—' }}</strong>
            <small>已迁移复盘记录</small>
          </article>
        </div>

        <div class="surface-card migration-card">
          <div class="migration-heading">
            <div>
              <Files />
              <span><strong>模块迁移状态</strong><small>新老系统数据与文件独立</small></span>
            </div>
            <ElTag type="success" effect="plain" round>迁移完成</ElTag>
          </div>
          <div class="migration-grid">
            <div v-for="module in systemOverview?.modules ?? []" :key="module.name">
              <CircleCheck />
              <span>{{ module.name }}</span>
              <small>已迁移</small>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.workspace-hero {
  position: relative;
  display: flex;
  min-height: 220px;
  padding: 36px 40px;
  overflow: hidden;
  align-items: center;
  justify-content: space-between;
  gap: 32px;
  border-radius: 18px;
  color: #fff;
  background:
    radial-gradient(circle at 82% 20%, rgba(95, 173, 255, 0.34), transparent 28%),
    linear-gradient(135deg, #15396f, #10284e 72%);
  box-shadow: 0 12px 32px rgba(18, 48, 91, 0.16);
}

.workspace-hero::after {
  position: absolute;
  right: -65px;
  bottom: -105px;
  width: 280px;
  height: 280px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 50%;
  content: '';
}

.hero-copy {
  position: relative;
  z-index: 1;
}

.hero-eyebrow {
  color: #84b8ff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.hero-copy h1 {
  margin: 9px 0 10px;
  font-size: 30px;
  line-height: 1.25;
}

.hero-copy p {
  margin: 0;
  color: #bdcde3;
  font-size: 14px;
}

.identity-tags {
  display: flex;
  margin-top: 20px;
  flex-wrap: wrap;
  gap: 8px;
}

.identity-tags :deep(.el-tag) {
  color: #d8e7fa;
  border-color: rgba(197, 220, 249, 0.24);
  background: rgba(255, 255, 255, 0.07);
}

.hero-action {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 18px;
}

.hero-symbol {
  display: grid;
  width: 68px;
  height: 68px;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 20px;
  color: #dbeafe;
  background: rgba(255, 255, 255, 0.08);
}

.hero-symbol svg { width: 31px; }

.section-heading {
  display: flex;
  margin-bottom: 17px;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.section-heading h2 {
  margin: 0 0 6px;
  color: #182740;
  font-size: 18px;
}

.section-heading p,
.section-heading > span {
  margin: 0;
  color: #8490a3;
  font-size: 12px;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.module-card {
  display: flex;
  min-height: 164px;
  padding: 22px;
  align-items: flex-start;
  gap: 16px;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.module-card:hover {
  border-color: #b9cff4;
  box-shadow: 0 10px 26px rgba(39, 73, 124, 0.09);
  transform: translateY(-2px);
}

.module-card:focus-visible {
  outline: 3px solid rgba(47, 111, 235, 0.24);
  outline-offset: 2px;
}

.module-icon {
  display: grid;
  width: 45px;
  height: 45px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 13px;
}

.module-icon svg { width: 21px; }
.module-icon.blue { color: #2f6feb; background: #eaf1ff; }
.module-icon.cyan { color: #168fa5; background: #e5f7f9; }
.module-icon.purple { color: #7356d8; background: #f0ecff; }
.module-icon.orange { color: #cc7824; background: #fff2e3; }
.module-icon.green { color: #14885f; background: #e7f7ef; }
.module-icon.slate { color: #60728c; background: #eef2f7; }
.module-icon.red { color: #c94a52; background: #fff0f0; }

.module-copy {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.module-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.module-title strong {
  color: #24344e;
  font-size: 15px;
}

.module-copy > span:nth-child(2) {
  min-height: 42px;
  margin-top: 10px;
  color: #7f8b9e;
  font-size: 12px;
  line-height: 1.7;
}

.module-copy small {
  display: flex;
  margin-top: 13px;
  align-items: center;
  gap: 5px;
  color: #2f6feb;
  font-size: 11px;
  font-weight: 600;
}

.module-copy small svg { width: 13px; }
.admin-section { padding-top: 3px; }
.admin-heading :deep(.el-tag) { display: inline-flex; gap: 5px; }
.admin-heading :deep(.el-tag svg) { width: 13px; }
.system-panel { min-height: 180px; }

.system-stats {
  display: grid;
  margin-bottom: 16px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.system-stat { padding: 21px 22px; }

.system-stat span,
.system-stat small {
  display: block;
  color: #8591a4;
  font-size: 11px;
}

.system-stat strong {
  display: block;
  margin: 10px 0 8px;
  overflow: hidden;
  color: #1f2e47;
  font-size: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.migration-card { padding: 22px 24px; }

.migration-heading {
  display: flex;
  padding-bottom: 17px;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #edf0f5;
}

.migration-heading > div {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #2f6feb;
}

.migration-heading svg { width: 22px; }
.migration-heading span,
.migration-heading strong,
.migration-heading small { display: block; }
.migration-heading strong { color: #27364e; font-size: 14px; }
.migration-heading small { margin-top: 4px; color: #8b97a8; font-size: 10px; }

.migration-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 24px;
}

.migration-grid > div {
  display: grid;
  min-height: 57px;
  align-items: center;
  border-bottom: 1px solid #f0f2f6;
  grid-template-columns: 22px 1fr auto;
  gap: 8px;
  color: #22a06b;
}

.migration-grid svg { width: 16px; }
.migration-grid span { color: #405069; font-size: 12px; }
.migration-grid small { color: #8c98a9; font-size: 10px; }

@media (max-width: 1180px) {
  .module-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .system-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 760px) {
  .workspace-hero { padding: 28px 24px; align-items: flex-start; flex-direction: column; }
  .hero-action { width: 100%; align-items: flex-start; }
  .hero-symbol { display: none; }
  .module-grid,
  .system-stats,
  .migration-grid { grid-template-columns: 1fr; }
  .section-heading { flex-direction: column; gap: 8px; }
}
</style>
