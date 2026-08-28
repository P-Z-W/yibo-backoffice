import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  currentUserRequest,
  changePasswordRequest,
  loginRequest,
  logoutRequest,
  type CurrentUser,
} from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const loaded = ref(false)
  const isAuthenticated = computed(() => Boolean(user.value))
  const mustChangePassword = computed(() => Boolean(user.value?.must_change_password))
  const isSystemAdmin = computed(
    () => Boolean(user.value?.roles?.includes('admin') || user.value?.role === 'admin'),
  )

  function can(permission: string) {
    return Boolean(user.value?.permissions?.[permission])
  }

  async function loadCurrentUser() {
    try {
      user.value = await currentUserRequest()
    } catch {
      user.value = null
    } finally {
      loaded.value = true
    }
  }

  async function login(username: string, password: string) {
    user.value = await loginRequest(username, password)
    loaded.value = true
  }

  async function logout() {
    try {
      await logoutRequest()
    } finally {
      user.value = null
      loaded.value = true
    }
  }

  async function changePassword(currentPassword: string, newPassword: string) {
    user.value = await changePasswordRequest(currentPassword, newPassword)
  }

  return {
    user,
    loaded,
    isAuthenticated,
    mustChangePassword,
    isSystemAdmin,
    can,
    loadCurrentUser,
    login,
    logout,
    changePassword,
  }
})
