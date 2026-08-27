import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'
import { pinia } from '../stores'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/',
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('../views/DashboardView.vue'),
          meta: { title: '工作台' },
        },
        {
          path: 'analytics',
          name: 'analytics',
          component: () => import('../views/AnalyticsView.vue'),
          meta: { title: '经营分析' },
        },
        {
          path: 'express',
          name: 'express-dashboard',
          component: () => import('../views/express/ExpressDashboardView.vue'),
          meta: { title: '快递对账 · 看板' },
        },
        {
          path: 'express/run',
          name: 'express-run',
          component: () => import('../views/express/ExpressRunView.vue'),
          meta: { title: '快递对账 · 运行' },
        },
        {
          path: 'express/history',
          name: 'express-history',
          component: () => import('../views/express/ExpressHistoryView.vue'),
          meta: { title: '快递对账 · 历史' },
        },
        {
          path: 'express/stats',
          name: 'express-stats',
          component: () => import('../views/express/ExpressStatsView.vue'),
          meta: { title: '快递对账 · 统计' },
        },
        {
          path: 'express/config',
          name: 'express-config',
          component: () => import('../views/express/ExpressConfigView.vue'),
          meta: { title: '快递对账 · 配置' },
        },
        {
          path: 'query',
          name: 'query-export',
          component: () => import('../views/QueryExportView.vue'),
          meta: { title: '数据查询 · 查询导出' },
        },
        {
          path: 'salary',
          name: 'salary',
          component: () => import('../views/SalaryView.vue'),
          meta: { title: '员工工资' },
        },
        {
          path: 'finance',
          component: () => import('../views/PlaceholderView.vue'),
          props: { title: '财务模块', description: '老系统仅有入口，本次已迁移为新版扩展位置。' },
          meta: { title: '财务模块' },
        },
        {
          path: 'reimbursement',
          component: () => import('../views/PlaceholderView.vue'),
          props: { title: '报销', description: '老系统仅有入口，本次已迁移为新版扩展位置。' },
          meta: { title: '报销' },
        },
        {
          path: 'storage',
          component: () => import('../views/PlaceholderView.vue'),
          props: { title: '仓储费', description: '老系统为规划模块，本次保留新版扩展位置。' },
          meta: { title: '仓储费' },
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
  document.title = `${String(to.meta.title ?? '工作台')} · 毅播云仓`
  return true
})

export default router
