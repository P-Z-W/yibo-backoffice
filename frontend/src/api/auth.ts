import { http } from './http'

export interface CurrentUser {
  id: number
  username: string
  display_name: string
  role: string
  role_name: string
  roles: string[]
  role_names: string[]
  team: string
  permissions: Record<string, string>
  must_change_password: boolean
}

interface AuthResponse {
  user: CurrentUser
}

export async function loginRequest(username: string, password: string) {
  const { data } = await http.post<AuthResponse>('/auth/login', { username, password })
  return data.user
}

export async function currentUserRequest() {
  const { data } = await http.get<AuthResponse>('/auth/me')
  return data.user
}

export async function logoutRequest() {
  await http.post('/auth/logout')
}

export async function changePasswordRequest(currentPassword: string, newPassword: string) {
  const { data } = await http.post<AuthResponse>('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
  return data.user
}
