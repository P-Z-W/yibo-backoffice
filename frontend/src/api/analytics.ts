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
}

export interface AnalyticsData {
  month: string
  previous_month: string
  metrics: AnalyticsMetric[]
  review: { summary: string; status: string }
  events: Array<{ id: number; category: string; title: string; description: string }>
  trend: Record<string, Array<{ month: string; value: number }>>
}

export async function getAnalytics(month: string) {
  return (await http.get<AnalyticsData>('/analytics', { params: { month } })).data
}

export async function saveAnalytics(data: {
  month: string
  metrics: Array<{ metric_id: number; value: number; note: string }>
  summary: string
}) {
  return (await http.put('/analytics', data)).data
}
