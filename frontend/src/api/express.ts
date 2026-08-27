import { http } from './http'

export interface ExpressStats {
  month: string
  total_orders: number
  matched_orders: number
  unmatched_orders: number
  total_amount: number
  team_stats: Array<{ team: string; amount: number; count: number }>
  express_stats: Array<{ name: string; amount: number; count: number; pct: number }>
  anomalies: Array<{ type: string; level: string; count: number; pct: number; samples: string[] }>
}

export interface ExpressOverview {
  process_month: string
  selected_month: string
  months: string[]
  stats: ExpressStats
  trend: Array<{ month: string; amount: number; orders: number; unmatched: number }>
  recent_runs: ExpressHistory[]
  job: ExpressJob
}

export interface ExpressHistory {
  month: string
  run_count: number
  last_result: string
  last_duration: string
  file_count: number
  size_bytes: number
  downloadable: boolean
}

export interface ExpressJob {
  running: boolean
  success: boolean
  period: string
  elapsed: string
  message: string
}

export interface TeamPrice {
  team: string
  st_fee: number
  st3: number
  st01: number
  zt_fee: number
  zt3: number
  zt01: number
  xixi_1kg_unit_price: number | null
  special_note: string
}

export async function getExpressOverview() {
  return (await http.get<ExpressOverview>('/express/overview')).data
}

export async function getExpressStats(month: string) {
  return (await http.get<ExpressStats>(`/express/stats/${month}`)).data
}

export async function getExpressHistory() {
  return (await http.get<ExpressHistory[]>('/express/history')).data
}

export async function uploadExpressFile(month: string, file: File) {
  const data = new FormData()
  data.append('month', month)
  data.append('file', file)
  return (await http.post('/express/upload', data, { timeout: 120000 })).data
}

export async function startExpressRun() {
  return (await http.post('/express/run')).data
}

export async function getExpressJob() {
  return (await http.get<ExpressJob>('/express/status')).data
}

export async function getTeamPrices() {
  return (await http.get<TeamPrice[]>('/express/config/customers')).data
}

export async function saveTeamPrices(rows: TeamPrice[]) {
  return (await http.put('/express/config/customers', { rows })).data
}

export async function getCarriers() {
  return (
    await http.get<Array<{ id: number; name: string; identify_column: string; enabled: boolean }>>(
      '/express/config/carriers',
    )
  ).data
}

export async function saveCarriers(
  carriers: Array<{ name: string; identify_column: string; enabled: boolean }>,
) {
  return (await http.put('/express/config/carriers', { carriers })).data
}

export async function getExpressSettings() {
  return (
    await http.get<{
      extend_days_before: number
      extend_days_after: number
      process_month: string
      sql_start_date: string
      sql_end_date: string
    }>('/express/config/settings')
  ).data
}

export async function saveExpressSettings(extend_days_before: number, extend_days_after: number) {
  return (
    await http.put('/express/config/settings', { extend_days_before, extend_days_after })
  ).data
}

export async function getPriceBook() {
  return (
    await http.get<{
      shentong: PriceRow[]
      zhongtong: PriceRow[]
      charge: Array<{ type: string; price: number }>
    }>('/express/config/prices')
  ).data
}

export interface PriceRow {
  province: string
  fee_3kg: number
  fee_over3kg: number
  unit_price: number
}

export async function savePriceBook(payload: {
  shentong: PriceRow[]
  zhongtong: PriceRow[]
  charge: Array<{ type: string; price: number }>
}) {
  return (await http.put('/express/config/prices', payload)).data
}
