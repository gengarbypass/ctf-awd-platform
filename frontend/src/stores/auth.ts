import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { LoginPayload, RegisterPayload, User } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)
  const isAdmin = computed(() => user.value?.role === 'ADMIN')

  async function restore() {
    if (ready.value) return
    try { user.value = await api.me() } catch { user.value = null } finally { ready.value = true }
  }
  async function login(payload: LoginPayload) { user.value = await api.login(payload); ready.value = true }
  async function register(payload: RegisterPayload) { user.value = await api.register(payload); ready.value = true }
  async function logout() { await api.logout(); user.value = null }
  function home() { return isAdmin.value ? '/admin' : '/dashboard' }

  return { user, ready, isAdmin, restore, login, register, logout, home }
})
