import { http } from './http'

export interface AnalyticsMetric {
  id: number
  code: string
  name: string
  category: string
  unit: string
  precision: number
  value: number | null
  previous_value: number | null
  change: number | null
  change_ratio: number | null
  note: string
  source_type: string | null
  source_label: string
  source_name: string | null
  updated_at: string | null
  updated_by_name: string | null
}

export interface AnalyticsData {
  month: string
  previous_month: string
  metrics: AnalyticsMetric[]
  review: {
    summary: string
    highlights: string
    issues: string
    risks: string
    next_plan: string
    status: 'draft' | 'completed' | 'archived'
    completed_at: string | null
    archived_at: string | null
    updated_at: string | null
    updated_by_name: string | null
  }
  completion: {
    completed: number
    total: number
    percent: number
    items: Array<{
      code: string
      name: string
      state: 'system' | 'uploaded' | 'summary_only' | 'missing'
      label: string
      source_name: string | null
      row_count: number
      updated_at: string | null
      updated_by_name: string | null
    }>
  }
  latest_activity: {
    updated_at: string
    updated_by_name: string | null
    source: string | null
  } | null
  events: Array<{ id: number; category: string; title: string; description: string }>
  trend: Record<string, Array<{ month: string; value: number }>>
}

export interface AnalyticsDetailType {
  code: string
  name: string
  description: string
  columns: string[]
  summary_hint: string
}

export interface AnalyticsDetailRow {
  id: number
  row_number: number
  values: Record<string, string | number | boolean | null>
  source_name: string
  imported_at: string
  is_template?: boolean
}

export interface ShippingSnapshotState {
  state: 'current' | 'review' | 'historical' | 'future'
  label: string
  hint: string
  can_system_sync: boolean
  window_start: string
  window_end: string
  version_count?: number
  captured_at?: string | null
  source_name?: string | null
}

export interface AnalyticsDetails {
  dataset: Pick<AnalyticsDetailType, 'code' | 'name' | 'description' | 'summary_hint'>
  month: string
  columns: string[]
  rows: AnalyticsDetailRow[]
  total: number
  page: number
  size: number
  summary: Record<string, number>
  snapshot: ShippingSnapshotState | null
  is_template?: boolean
  batches: Array<{
    original_name: string
    sheet_name: string
    mode: string
    row_count: number
    imported_at: string
    imported_by_name: string | null
  }>
}

export interface AnalyticsImportPreview {
  original_name: string
  sheet_name: string
  columns: string[]
  rows: Array<Record<string, string | number | boolean | null>>
  row_count: number
  warnings: string[]
  summary: Record<string, number>
  match_result: {
    matched_count: number
    unmatched_count: number
    unmatched_teams: string[]
    added_count?: number
    preserved_count?: number
  } | null
}

export interface ShippingSystemPreview {
  source_name: string
  month_start: string
  month_end: string
  columns: string[]
  rows: Array<Record<string, string | number | null>>
  row_count: number
  total: number
  conditions: string[]
  snapshot: ShippingSnapshotState
  warnings: string[]
  blocking: boolean
  requires_confirmation: boolean
  current_total: number
  current_team_count: number
}

export type ReturnSystemPreview = ShippingSystemPreview

export async function getAnalytics(month: string) {
  return (await http.get<AnalyticsData>('/analytics', { params: { month } })).data
}

export async function saveAnalytics(data: {
  month: string
  metrics: Array<{ metric_id: number; value: number; note: string }>
  summary: string
  highlights: string
  issues: string
  risks: string
  next_plan: string
}) {
  return (await http.put('/analytics', data)).data
}

export async function updateAnalyticsStatus(
  month: string,
  status: 'draft' | 'completed' | 'archived',
) {
  return (await http.put('/analytics/status', { month, status })).data
}

export async function getAnalyticsDetailTypes() {
  return (await http.get<AnalyticsDetailType[]>('/analytics/detail-types')).data
}

export async function getAnalyticsDetails(
  type: string,
  month: string,
  page = 1,
  size = 50,
  options?: { search?: string; sortOrder?: '' | 'asc' | 'desc' },
) {
  return (
    await http.get<AnalyticsDetails>(`/analytics/details/${type}`, {
      params: {
        month,
        page,
        size,
        search: options?.search || undefined,
        sort_order: options?.sortOrder || undefined,
      },
    })
  ).data
}

export async function previewAnalyticsImport(type: string, file: File, month?: string) {
  const data = new FormData()
  data.append('file', file)
  return (
    await http.post<AnalyticsImportPreview>(`/analytics/details/${type}/preview`, data, {
      params: { month: month || undefined },
      timeout: 120000,
    })
  ).data
}

export async function previewShippingSystemData(month: string) {
  return (
    await http.get<ShippingSystemPreview>(
      '/analytics/details/shipping_orders/system-preview',
      { params: { month }, timeout: 120000 },
    )
  ).data
}

export async function syncShippingSystemData(month: string, confirmWarning = false) {
  return (
    await http.post<{
      ok: boolean
      message: string
      row_count: number
      total: number
      snapshot: ShippingSnapshotState
      warnings: string[]
    }>(
      '/analytics/details/shipping_orders/system-sync',
      undefined,
      { params: { month, confirm_warning: confirmWarning }, timeout: 120000 },
    )
  ).data
}

export async function previewReturnSystemData(month: string) {
  return (
    await http.get<ReturnSystemPreview>(
      '/analytics/details/return_items/system-preview',
      { params: { month }, timeout: 120000 },
    )
  ).data
}

export async function syncReturnSystemData(month: string, confirmWarning = false) {
  return (
    await http.post<{
      ok: boolean
      message: string
      row_count: number
      total: number
      snapshot: ShippingSnapshotState
      warnings: string[]
    }>(
      '/analytics/details/return_items/system-sync',
      undefined,
      { params: { month, confirm_warning: confirmWarning }, timeout: 120000 },
    )
  ).data
}

export async function exportReturnItems(
  month: string,
  options?: { search?: string; sortOrder?: '' | 'asc' | 'desc' },
) {
  return (
    await http.get<Blob>('/analytics/details/return_items/export', {
      params: {
        month,
        search: options?.search || undefined,
        sort_order: options?.sortOrder || undefined,
      },
      responseType: 'blob',
      timeout: 120000,
    })
  ).data
}

export async function updateShippingRemark(rowId: number, month: string, remark: string) {
  return (
    await http.patch<{ ok: boolean; row_id: number; remark: string }>(
      `/analytics/details/shipping_orders/rows/${rowId}/remark`,
      { month, remark },
    )
  ).data
}

export async function updateStaffingAnalysis(rowId: number, month: string, analysis: string) {
  return (
    await http.patch<{ ok: boolean; row_id: number; analysis: string }>(
      `/analytics/details/staffing/rows/${rowId}/analysis`,
      { month, analysis },
    )
  ).data
}

export async function updateStaffingInputs(
  rowId: number,
  payload: {
    month: string
    team_name: string
    regular_staff: number
    optimal_staff: number | null
    monthly_output: number | null
    optimal_monthly_output: number | null
  },
) {
  return (
    await http.patch<{
      ok: boolean
      row_id: number
      values: AnalyticsDetailRow['values']
      regular_total: number
    }>(`/analytics/details/staffing/rows/${rowId}/inputs`, payload)
  ).data
}

export async function exportShippingOrders(payload: {
  month: string
  scope: 'filtered' | 'selected'
  row_ids: number[]
  columns: Array<'团队名称' | '发货单量' | '数据发货占比' | '备注'>
  search: string
  sort_order: '' | 'asc' | 'desc'
}) {
  return (
    await http.post<Blob>('/analytics/details/shipping_orders/export', payload, {
      responseType: 'blob',
      timeout: 120000,
    })
  ).data
}

export async function exportStaffing(month: string) {
  return (
    await http.get<Blob>('/analytics/details/staffing/export', {
      params: { month },
      responseType: 'blob',
      timeout: 120000,
    })
  ).data
}

export async function importAnalyticsDetails(
  type: string,
  month: string,
  mode: 'replace' | 'append',
  file: File,
) {
  const data = new FormData()
  data.append('month', month)
  data.append('mode', mode)
  data.append('file', file)
  return (
    await http.post<{
      ok: boolean
      message: string
      row_count: number
      warnings: string[]
      matched_count?: number
      added_count?: number
      preserved_count?: number
      unmatched_teams?: string[]
      updated_metrics: Array<{ code: string; name: string; value: number }>
    }>(`/analytics/details/${type}/import`, data, { timeout: 120000 })
  ).data
}
