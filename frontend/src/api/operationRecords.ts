import { http } from './http'

export type OperationDataset = 'customer_changes' | 'value_added' | 'service_issues' | 'short_video'

export interface OperationRecord {
  id: number
  month: string
  created_at: string
  updated_at: string
  [key: string]: string | number
}

export interface OperationRecordList {
  records: OperationRecord[]
  total: number
  page: number
  size: number
  summary: Record<string, number>
}

export interface OperationImportResult {
  ok: boolean
  created_count: number
  updated_count: number
  skipped_count: number
  total_count: number
}

export interface CustomerSourcePreviewRow {
  team_id: number | null
  team_name: string
  created_time: string
  cooperation_type: number | null
  stock_send_price: number | null
  viewable: boolean | null
  registered: boolean
  archived: boolean
}

export interface CustomerSourcePreview {
  source: string
  filters: {
    cooperation_type: number
    stock_send_price_lt: number
    stock_send_price_null_included: boolean
  }
  total: number
  registered_total: number
  archived_total: number
  pending_total: number
  rows: CustomerSourcePreviewRow[]
}

export interface CustomerSourceSyncResult {
  ok: boolean
  created_count: number
  skipped_existing: number
  skipped_invalid: number
  skipped_archived: number
  affected_months: string[]
}

export async function getCustomerSourcePreview() {
  return (
    await http.get<CustomerSourcePreview>('/operation-records/customer_changes/source-preview', {
      timeout: 60000,
    })
  ).data
}

export async function syncCustomerSource() {
  return (
    await http.post<CustomerSourceSyncResult>('/operation-records/customer_changes/source-sync', undefined, {
      timeout: 60000,
    })
  ).data
}

export async function getOperationRecords(
  dataset: OperationDataset,
  params: {
    month: string
    keyword?: string
    filter_value?: string
    page: number
    size: number
  },
) {
  return (await http.get<OperationRecordList>(`/operation-records/${dataset}`, { params })).data
}

export async function createOperationRecord(
  dataset: OperationDataset,
  payload: Record<string, unknown>,
) {
  return (await http.post<OperationRecord>(`/operation-records/${dataset}`, payload)).data
}

export async function updateOperationRecord(
  dataset: OperationDataset,
  id: number,
  payload: Record<string, unknown>,
) {
  return (await http.put<OperationRecord>(`/operation-records/${dataset}/${id}`, payload)).data
}

export async function deleteOperationRecord(dataset: OperationDataset, id: number) {
  return (await http.delete<{ ok: boolean }>(`/operation-records/${dataset}/${id}`)).data
}

export async function downloadOperationTemplate(dataset: OperationDataset) {
  return http.get<Blob>(`/operation-records/${dataset}/template`, { responseType: 'blob' })
}

export async function importOperationRecords(
  dataset: OperationDataset,
  file: File,
  month: string,
) {
  const form = new FormData()
  form.append('file', file)
  return (
    await http.post<OperationImportResult>(`/operation-records/${dataset}/import`, form, {
      params: { month },
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
  ).data
}

export async function exportOperationRecords(
  dataset: OperationDataset,
  params: { month: string; keyword?: string; filter_value?: string },
) {
  return http.get<Blob>(`/operation-records/${dataset}/export`, {
    params,
    responseType: 'blob',
    timeout: 60000,
  })
}
