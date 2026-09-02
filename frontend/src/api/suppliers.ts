import { http } from './http'

export interface SupplierRecord {
  id: number
  name: string
  contact_name: string
  contact_phone: string
  address: string
  cooperation_start_date: string
  product_types: string
  note: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SupplierPayload {
  name: string
  contact_name: string
  contact_phone: string
  address: string
  cooperation_start_date: string | null
  product_types: string
  note: string
  change_month: string
  change_note: string
}

export interface SupplierChangeRecord {
  id: number
  supplier_id: number
  supplier_name: string
  change_month: string
  change_type: 'created' | 'updated' | 'activated' | 'deactivated'
  change_note: string
  operator_name: string
  snapshot: Record<string, unknown>
  created_at: string
}

export interface SupplierImportResult {
  ok: boolean
  message: string
  created_count: number
  updated_count: number
  skipped_count: number
  total_count: number
}

export async function getSuppliers(params: {
  keyword?: string
  active?: boolean
  month: string
  page: number
  size: number
}) {
  return (
    await http.get<{
      records: SupplierRecord[]
      total: number
      page: number
      size: number
      summary: {
        total: number
        active: number
        inactive: number
        month_added: number
        month_changed: number
      }
    }>('/suppliers', { params })
  ).data
}

export async function getSupplierChanges(month: string) {
  return (
    await http.get<SupplierChangeRecord[]>('/suppliers/changes', { params: { month } })
  ).data
}

export async function createSupplier(payload: SupplierPayload) {
  return (await http.post<SupplierRecord>('/suppliers', payload)).data
}

export async function updateSupplier(id: number, payload: SupplierPayload) {
  return (await http.put<SupplierRecord>(`/suppliers/${id}`, payload)).data
}

export async function updateSupplierStatus(
  id: number,
  payload: { is_active: boolean; change_month: string; change_note: string },
) {
  return (await http.patch<SupplierRecord>(`/suppliers/${id}/status`, payload)).data
}

export async function downloadSupplierTemplate() {
  return http.get<Blob>('/suppliers/template', { responseType: 'blob' })
}

export async function importSuppliers(file: File, month: string) {
  const form = new FormData()
  form.append('file', file)
  return (
    await http.post<SupplierImportResult>('/suppliers/import', form, {
      params: { month },
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 60000,
    })
  ).data
}

export async function exportSuppliers(params: { keyword?: string; active?: boolean }) {
  return http.get<Blob>('/suppliers/export', {
    params,
    responseType: 'blob',
    timeout: 60000,
  })
}
