<script setup lang="ts">
import { computed, ref } from 'vue'
import { Send } from '@lucide/vue'
import { api, isDemo } from '@/api/client'
import type { FlagResult } from '@/api/types'
import { signed, submissionResult } from '@/utils/format'
import StatusTag from './StatusTag.vue'

const emit = defineEmits<{ accepted: [] }>()
const flag = ref('')
const loading = ref(false)
const error = ref('')
const result = ref<FlagResult | null>(null)
const resultMeta = computed(() => result.value ? submissionResult[result.value.result] : null)

async function submit() {
  error.value = ''
  result.value = null
  if (!flag.value.trim()) { error.value = '请输入要验判的 Flag。'; return }
  loading.value = true
  try {
    result.value = await api.submitFlag(flag.value.trim(), crypto.randomUUID())
    if (result.value.result === 'ACCEPTED') { flag.value = ''; emit('accepted') }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : '提交失败，请稍后重试。'
  } finally { loading.value = false }
}
</script>

<template>
  <form class="flag-form" @submit.prevent="submit">
    <label for="flag-input">提交 Flag</label>
    <p class="field-help">提交其他队伍当前有效的 Flag。同一 Flag 重复提交不会再次计分。</p>
    <div class="flag-form__row">
      <input id="flag-input" v-model="flag" class="input code-input" name="flag" type="text" autocomplete="off" spellcheck="false" placeholder="flag{…}" :aria-invalid="!!error" aria-describedby="flag-help" @input="error = ''; result = null" />
      <button class="button button--primary" type="submit" :disabled="loading" :aria-busy="loading"><Send :size="16" aria-hidden="true" />{{ loading ? '验判中' : '提交验判' }}</button>
    </div>
    <p id="flag-help" class="field-help" :class="{ 'field-error': error }" aria-live="polite">{{ error || (isDemo ? '演示可提交 flag{t02-web-r24}，重复提交可查看去重结果。' : '请确认 Flag 来源和当前比赛轮次。') }}</p>
    <div v-if="result && resultMeta" class="submission-feedback" :class="`feedback--${resultMeta.tone}`" role="status">
      <StatusTag :label="resultMeta.label" :tone="resultMeta.tone" />
      <template v-if="result.result === 'ACCEPTED'"><strong>本队 {{ signed(result.attacker_delta) }} 分</strong><span>当前 {{ result.attacker_score }} 分，对方 {{ signed(result.victim_delta) }} 分</span></template>
      <span v-else>本次提交不产生分数变化。</span>
    </div>
  </form>
</template>
