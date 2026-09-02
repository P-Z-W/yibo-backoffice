export const viewLoaders = {
  login: () => import('../views/LoginView.vue'),
  changePassword: () => import('../views/ChangePasswordView.vue'),
  forbidden: () => import('../views/ForbiddenView.vue'),
  dashboard: () => import('../views/DashboardView.vue'),
  analytics: () => import('../views/AnalyticsView.vue'),
  suppliers: () => import('../views/SupplierManagementView.vue'),
  operationRecords: () => import('../views/OperationRecordsView.vue'),
  expressDashboard: () => import('../views/express/ExpressDashboardView.vue'),
  expressRun: () => import('../views/express/ExpressRunView.vue'),
  expressHistory: () => import('../views/express/ExpressHistoryView.vue'),
  expressStats: () => import('../views/express/ExpressStatsView.vue'),
  expressConfig: () => import('../views/express/ExpressConfigView.vue'),
  queryExport: () => import('../views/QueryExportView.vue'),
  salary: () => import('../views/SalaryView.vue'),
  placeholder: () => import('../views/PlaceholderView.vue'),
  reimbursement: () => import('../views/ReimbursementView.vue'),
  access: () => import('../views/AccessManagementView.vue'),
}

const routeLoaders: Record<string, () => Promise<unknown>> = {
  '/': viewLoaders.dashboard,
  '/analytics': viewLoaders.analytics,
  '/suppliers': viewLoaders.suppliers,
  '/customers': viewLoaders.operationRecords,
  '/value-added': viewLoaders.operationRecords,
  '/customer-service': viewLoaders.operationRecords,
  '/short-video': viewLoaders.operationRecords,
  '/express': viewLoaders.expressDashboard,
  '/express/run': viewLoaders.expressRun,
  '/express/history': viewLoaders.expressHistory,
  '/express/stats': viewLoaders.expressStats,
  '/express/config': viewLoaders.expressConfig,
  '/query': viewLoaders.queryExport,
  '/finance': viewLoaders.placeholder,
  '/salary': viewLoaders.salary,
  '/reimbursement': viewLoaders.reimbursement,
  '/storage': viewLoaders.placeholder,
  '/access': viewLoaders.access,
}
const preloadTasks = new Map<string, Promise<unknown>>()

export function prefetchRoute(path: string) {
  const loader = routeLoaders[path]
  if (!loader || preloadTasks.has(path)) return
  const task = loader().catch(() => preloadTasks.delete(path))
  preloadTasks.set(path, task)
}
