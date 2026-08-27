import { http } from './http'

export interface QueryEntry {
  id: number
  group_name: string
  query_name: string
  filename: string
  sql_content: string
  sql_preview: string
}

export interface QueryHistory {
  date: string
  file_count: number
  files: string[]
}

export async function getQueryWorkspace() {
  return (
    await http.get<{
      groups: Record<string, QueryEntry[]>
      history: QueryHistory[]
      job: { running: boolean; success: boolean; files: string[]; message: string }
    }>('/query-export/configs')
  ).data
}

export async function addQuery(group_name: string) {
  return (
    await http.post<QueryEntry>('/query-export/configs', { group_name, filename: '', sql_content: '' })
  ).data
}

export async function saveQuery(entry: QueryEntry) {
  return (
    await http.put<QueryEntry>(`/query-export/configs/${entry.id}`, {
      group_name: entry.group_name,
      filename: entry.filename,
      sql_content: entry.sql_content,
    })
  ).data
}

export async function deleteQuery(id: number) {
  await http.delete(`/query-export/configs/${id}`)
}

export async function runQueries(entry_ids: number[]) {
  return (await http.post('/query-export/run', entry_ids)).data
}
