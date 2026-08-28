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
      state: 'uploaded' | 'summary_only' | 'missing'
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
}

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

export async function getAnalyticsDetails(type: string, month: string, page = 1, size = 50) {
  return (
    await http.get<AnalyticsDetails>(`/analytics/details/${type}`, {
      params: { month, page, size },
    })
  ).data
}

export async function previewAnalyticsImport(type: string, file: File) {
  const data = new FormData()
  data.append('file', file)
  return (
    await http.post<AnalyticsImportPreview>(`/analytics/details/${type}/preview`, data, {
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
      updated_metrics: Array<{ code: string; name: string; value: number }>
    }>(`/analytics/details/${type}/import`, data, { timeout: 120000 })
  ).data
}
