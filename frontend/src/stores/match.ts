import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api/client'
import type { Match } from '@/api/types'
import { matchStatus } from '@/utils/format'

export const useMatchStore = defineStore('match', () => {
  const match = ref<Match | null>(null)
  const loading = ref(false)
  const clock = ref(Date.now())
  let timer: number | undefined

  async function load() {
    loading.value = true
    try { match.value = await api.match() } finally { loading.value = false }
  }
  function startClock() {
    if (timer) return
    timer = window.setInterval(() => { clock.value = Date.now() }, 1000)
  }
  function stopClock() { if (timer) window.clearInterval(timer); timer = undefined }
  const statusLabel = computed(() => {
    if (!match.value) return '暂无比赛'
    const state = matchStatus[match.value.status]
    return state?.label ?? '状态未知'
  })
  const remainingSeconds = computed(() => {
    if (!match.value || !['RUNNING', 'PAUSED'].includes(match.value.status)) return 0
    const reference = match.value.status === 'PAUSED' && match.value.paused_at ? new Date(match.value.paused_at).getTime() : clock.value
    return Math.max(0, (new Date(match.value.ends_at).getTime() - reference) / 1000)
  })
  const roundRemainingSeconds = computed(() => {
    if (!match.value || match.value.status !== 'RUNNING') return 0
    const elapsed = Math.floor(clock.value / 1000)
    return match.value.round_seconds - (elapsed % match.value.round_seconds)
  })
  return { match, loading, remainingSeconds, roundRemainingSeconds, statusLabel, load, startClock, stopClock }
})
