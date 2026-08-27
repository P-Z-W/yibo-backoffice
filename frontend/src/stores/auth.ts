import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  currentUserRequest,
  loginRequest,
  logoutRequest,
  type CurrentUser,
} from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<CurrentUser | null>(null)
  const loaded = ref(false)
  const isAuthenticated = computed(() => Boolean(user.value))

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

  return { user, loaded, isAuthenticated, loadCurrentUser, login, logout }
})
