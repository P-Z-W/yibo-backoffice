import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'
import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'
import { viewLoaders } from './viewLoaders'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: viewLoaders.login,
      meta: { title: '登录' },
    },
    {
      path: '/change-password',
      name: 'change-password',
      component: viewLoaders.changePassword,
      meta: { requiresAuth: true, title: '修改密码' },
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: viewLoaders.forbidden,
      meta: { requiresAuth: true, title: '无权访问' },
    },
    {
      path: '/',
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: viewLoaders.dashboard,
          meta: { title: '工作台', permission: 'dashboard.view' },
        },
        {
          path: 'analytics',
          name: 'analytics',
          component: viewLoaders.analytics,
          meta: { title: '经营分析', permission: 'analytics.view' },
        },
        {
          path: 'suppliers',
          name: 'suppliers',
          component: viewLoaders.suppliers,
          meta: { title: '供应商管理', permission: 'suppliers.view' },
        },
        {
          path: 'customers',
          name: 'customers',
          component: viewLoaders.operationRecords,
          props: { dataset: 'customer_changes' },
          meta: { title: '客户管理', permission: 'operations_data.view' },
        },
        {
          path: 'value-added',
          name: 'value-added',
          component: viewLoaders.operationRecords,
          props: { dataset: 'value_added' },
          meta: { title: '增值服务', permission: 'operations_data.view' },
        },
        {
          path: 'customer-service',
          name: 'customer-service',
          component: viewLoaders.operationRecords,
          props: { dataset: 'service_issues' },
          meta: { title: '客户服务管理', permission: 'operations_data.view' },
        },
        {
          path: 'short-video',
          name: 'short-video',
          component: viewLoaders.operationRecords,
          props: { dataset: 'short_video' },
          meta: { title: '短视频管理', permission: 'operations_data.view' },
        },
        {
          path: 'express',
          name: 'express-dashboard',
          component: viewLoaders.expressDashboard,
          meta: { title: '快递对账 · 看板', permission: 'express.view' },
        },
        {
          path: 'express/run',
          name: 'express-run',
          component: viewLoaders.expressRun,
          meta: { title: '快递对账 · 运行', permission: 'express.run' },
        },
        {
          path: 'express/history',
          name: 'express-history',
          component: viewLoaders.expressHistory,
          meta: { title: '快递对账 · 历史', permission: 'express.view' },
        },
        {
          path: 'express/stats',
          name: 'express-stats',
          component: viewLoaders.expressStats,
          meta: { title: '快递对账 · 统计', permission: 'express.view' },
        },
        {
          path: 'express/config',
          name: 'express-config',
          component: viewLoaders.expressConfig,
          meta: { title: '快递对账 · 配置', permission: 'express.configure' },
        },
        {
          path: 'query',
          name: 'query-export',
          component: viewLoaders.queryExport,
          meta: { title: '数据查询 · 查询导出', permission: 'query.view' },
        },
        {
          path: 'salary',
          name: 'salary',
          component: viewLoaders.salary,
          meta: { title: '员工工资', permission: 'salary.view' },
        },
        {
          path: 'finance',
          component: viewLoaders.placeholder,
          props: { title: '财务模块', description: '老系统仅有入口，本次已迁移为新版扩展位置。' },
          meta: { title: '财务模块', permission: 'salary.view' },
        },
        {
          path: 'reimbursement',
          component: viewLoaders.reimbursement,
          meta: { title: '报销', permission: 'reimbursement.view' },
        },
        {
          path: 'storage',
          component: viewLoaders.placeholder,
          props: { title: '仓储费', description: '老系统为规划模块，本次保留新版扩展位置。' },
          meta: { title: '仓储费', permission: 'storage.view' },
        },
        {
          path: 'access',
          name: 'access-management',
          component: viewLoaders.access,
          meta: { title: '账号与权限', systemAdminOnly: true },
        },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)
  if (!auth.loaded) await auth.loadCurrentUser()

  if (to.name === 'login' && auth.isAuthenticated) return { name: 'dashboard' }
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.systemAdminOnly && !auth.isSystemAdmin) return { name: 'forbidden' }
  const permission = String(to.meta.permission || '')
  if (permission && !auth.can(permission)) return { name: 'forbidden' }
  document.title = `${String(to.meta.title ?? '工作台')} · 毅播云仓`
  return true
})

export default router
