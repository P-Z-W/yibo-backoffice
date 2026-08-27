import { http } from './http'

export interface SalaryRecord {
  id: number
  name: string
  team: string
  year_month: string
  base_salary: number
  bonus: number
  deduction: number
  total: number
  note: string
}

export type SalaryPayload = Omit<SalaryRecord, 'id' | 'total'>

export async function getSalary(month: string) {
  return (
    await http.get<{
      records: SalaryRecord[]
      summary: { employees: number; base_salary: number; bonus: number; deduction: number; total: number }
    }>('/salary', { params: { month } })
  ).data
}

export async function addSalary(payload: SalaryPayload) {
  return (await http.post<SalaryRecord>('/salary', payload)).data
}

export async function saveSalary(id: number, payload: SalaryPayload) {
  return (await http.put<SalaryRecord>(`/salary/${id}`, payload)).data
}

export async function deleteSalary(id: number) {
  await http.delete(`/salary/${id}`)
}
