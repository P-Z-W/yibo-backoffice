import { http } from './http'

export interface AccessOverview {
  summary: { total: number; active: number; disabled: number; administrators: number }
  teams: string[]
}

export interface ManagedUser {
  id: number
  username: string
  display_name: string
  role: string
  role_name: string
  roles: string[]
  role_names: string[]
  team: string
  is_active: boolean
  must_change_password: boolean
  latest_password: string | null
  last_login_at: string | null
  created_at: string | null
}

export interface PermissionDefinition {
  code: string
  name: string
  module: string
  action: string
  sort_order: number
  supports_scope: boolean
}

export interface RoleDefinition {
  code: string
  name: string
  description: string
  is_system: boolean
  user_count: number
  permissions: Record<string, string>
}

export interface AuditEntry {
  id: number
  operator_name: string
  action: string
  resource: string
  detail: string
  ip_address: string
  created_at: string
}

export interface UserPayload {
  username?: string
  display_name: string
  team: string
  roles: string[]
  is_active?: boolean
}

export interface RolePayload {
  name: string
  description: string
  permissions: Record<string, string>
}

export async function getAccessOverview() {
  return (await http.get<AccessOverview>('/access/overview')).data
}

export async function getUsers(params: Record<string, string | boolean | undefined>) {
  return (await http.get<ManagedUser[]>('/access/users', { params })).data
}

export async function createUser(payload: UserPayload) {
  return (
    await http.post<{ user: ManagedUser; temporary_password: string }>('/access/users', payload)
  ).data
}

export async function updateUser(id: number, payload: UserPayload) {
  return (await http.put<ManagedUser>(`/access/users/${id}`, payload)).data
}

export async function resetUserPassword(id: number) {
  return (
    await http.post<{ temporary_password: string }>(`/access/users/${id}/reset-password`)
  ).data
}

export async function getRoles() {
  return (await http.get<RoleDefinition[]>('/access/roles')).data
}

export async function getPermissions() {
  return (await http.get<PermissionDefinition[]>('/access/permissions')).data
}

export async function createRole(payload: RolePayload) {
  return (await http.post<RoleDefinition>('/access/roles', payload)).data
}

export async function updateRole(code: string, payload: RolePayload) {
  return (await http.put<RoleDefinition>(`/access/roles/${code}`, payload)).data
}

export async function deleteRole(code: string) {
  await http.delete(`/access/roles/${code}`)
}

export async function getAuditLogs(params: Record<string, string | number | undefined>) {
  return (await http.get<AuditEntry[]>('/access/audit', { params })).data
}
