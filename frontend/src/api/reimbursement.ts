import { http } from './http'

export interface ReimbursementItem {
  id?: number
  expense_date: string
  category: string
  amount: number
  related_number: string
  description: string
}

export interface ReimbursementAttachment {
  id: number
  original_name: string
  content_type: string
  size_bytes: number
  url: string
  duplicate?: boolean
  created_at?: string
}

export interface ApprovalRecord {
  id: number
  actor_name: string
  actor_role: string
  action: string
  from_status: string
  to_status: string
  comment: string
  created_at: string
}

export interface ReimbursementRecord {
  id: number
  number: string
  applicant_id: number
  applicant_name: string
  team: string
  status: string
  status_label: string
  total_amount: number
  item_count: number
  item_summary: string
  attachment_count: number
  note: string
  finance_approval_required: boolean
  exported: boolean
  exported_at: string
  export_batch: string
  submitted_at: string
  created_at: string
  updated_at: string
  can_edit: boolean
  can_approve: boolean
  items?: ReimbursementItem[]
  attachments?: ReimbursementAttachment[]
  approval_records?: ApprovalRecord[]
}

export interface ReimbursementPayload {
  applicant_name: string
  team: string
  note: string
  items: ReimbursementItem[]
}

export interface ReimbursementListResponse {
  records: ReimbursementRecord[]
  summary: {
    pending_supervisor: number
    pending_finance: number
    pending_export: number
    month_approved_count: number
    month_approved_amount: number
  }
  config: {
    finance_approval_enabled: boolean
    teams: string[]
    expense_categories: string[]
  }
  permissions: { can_configure: boolean; can_export: boolean }
}

export interface BatchImportClaimPreview {
  group_key: string
  applicant_name: string
  team: string
  note: string
  item_count: number
  total_amount: number
  valid: boolean
  issues: string[]
}

export interface BatchImportPreview {
  claims: BatchImportClaimPreview[]
  errors: Array<{ row?: number; group?: string; message: string }>
  claim_count: number
  item_count: number
  total_amount: number
  can_import: boolean
}

export interface BatchImportResult {
  claim_count: number
  item_count: number
  total_amount: number
  status: string
  records: Array<{ id: number; number: string; applicant_name: string }>
}

export async function getReimbursements(params: Record<string, string>) {
  const query = Object.fromEntries(
    Object.entries(params).filter(([, value]) => value.trim() !== ''),
  )
  return (await http.get<ReimbursementListResponse>('/reimbursements', { params: query })).data
}

export async function getReimbursement(id: number) {
  return (await http.get<ReimbursementRecord>(`/reimbursements/${id}`)).data
}

export async function createReimbursement(payload: ReimbursementPayload) {
  return (await http.post<ReimbursementRecord>('/reimbursements', payload)).data
}

export async function updateReimbursement(id: number, payload: ReimbursementPayload) {
  return (await http.put<ReimbursementRecord>(`/reimbursements/${id}`, payload)).data
}

export async function deleteReimbursement(id: number) {
  await http.delete(`/reimbursements/${id}`)
}

export async function submitReimbursement(id: number) {
  return (await http.post<ReimbursementRecord>(`/reimbursements/${id}/submit`)).data
}

export async function approveReimbursement(id: number, comment = '') {
  return (await http.post<ReimbursementRecord>(`/reimbursements/${id}/approve`, { comment })).data
}

export async function returnReimbursement(id: number, comment: string) {
  return (await http.post<ReimbursementRecord>(`/reimbursements/${id}/return`, { comment })).data
}

export async function saveReimbursementConfig(financeApprovalEnabled: boolean) {
  return (
    await http.put<{ finance_approval_enabled: boolean }>('/reimbursements/config', {
      finance_approval_enabled: financeApprovalEnabled,
    })
  ).data
}

export async function previewReimbursementImport(file: File) {
  const data = new FormData()
  data.append('file', file)
  return (
    await http.post<{ items: ReimbursementItem[]; errors: { row: number; message: string }[]; count: number }>(
      '/reimbursements/import/preview',
      data,
      { timeout: 120000 },
    )
  ).data
}

export async function previewBatchReimbursementImport(file: File) {
  const data = new FormData()
  data.append('file', file)
  return (
    await http.post<BatchImportPreview>('/reimbursements/batch/preview', data, {
      timeout: 120000,
    })
  ).data
}

export async function importBatchReimbursements(file: File, submit: boolean) {
  const data = new FormData()
  data.append('file', file)
  data.append('submit', String(submit))
  return (
    await http.post<BatchImportResult>('/reimbursements/batch/import', data, {
      timeout: 120000,
    })
  ).data
}

export async function uploadReimbursementAttachment(id: number, file: File) {
  const data = new FormData()
  data.append('file', file)
  return (
    await http.post<ReimbursementAttachment>(`/reimbursements/${id}/attachments`, data, {
      timeout: 120000,
    })
  ).data
}

export async function deleteReimbursementAttachment(id: number, attachmentId: number) {
  await http.delete(`/reimbursements/${id}/attachments/${attachmentId}`)
}

export async function exportReimbursements(ids: number[]) {
  const { data } = await http.get<Blob>('/reimbursements/export/xlsx', {
    params: { ids: ids.join(',') },
    responseType: 'blob',
    timeout: 120000,
  })
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = `报销数据_${new Date().toISOString().slice(0, 10)}.xlsx`
  link.click()
  URL.revokeObjectURL(url)
}

export async function markReimbursementsExported(ids: number[]) {
  return (await http.post<{ batch: string; count: number }>('/reimbursements/export/mark', { ids })).data
}
