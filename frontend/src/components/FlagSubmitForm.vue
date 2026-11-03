<script setup lang="ts">
import { computed, ref } from 'vue'
import { CircleCheck, CircleX, Send } from '@lucide/vue'
import { api, isDemo } from '@/api/client'
import type { FlagResult } from '@/api/types'
import { signed, submissionResult } from '@/utils/format'
import StatusTag from './StatusTag.vue'

const emit = defineEmits<{ accepted: [] }>()
const flag = ref('')
const loading = ref(false)
const error = ref('')
const result = ref<FlagResult | null>(null)
const feedbackOpen = ref(false)
const resultMeta = computed(() => result.value ? submissionResult[result.value.result] : null)
const accepted = computed(() => result.value?.result === 'ACCEPTED')
const failureReason = computed(() => {
  switch (result.value?.result) {
    case 'DUPLICATE': return '这个 Flag 本队已经提交过，本次不会重复计分。'
    case 'OWN_TEAM': return '不能提交本队自己的 Flag。'
    case 'EXPIRED': return '这个 Flag 已过期，请获取当前轮次的新 Flag。'
    case 'INVALID': return 'Flag 不正确或格式无效，请确认后重试。'
    case 'MATCH_NOT_RUNNING': return '比赛尚未开始、已暂停或已结束，本次提交不计分。'
    default: return '本次提交未通过验判。'
  }
})

async function submit() {
  error.value = ''
  result.value = null
  feedbackOpen.value = false
  if (!flag.value.trim()) { error.value = '请输入要验判的 Flag。'; return }
  loading.value = true
  try {
    result.value = await api.submitFlag(flag.value.trim(), crypto.randomUUID())
    feedbackOpen.value = true
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
      <input id="flag-input" v-model="flag" class="input code-input" name="flag" type="text" autocomplete="off" spellcheck="false" placeholder="flag{…}" :aria-invalid="!!error" aria-describedby="flag-help" @input="error = ''; result = null; feedbackOpen = false" />
      <button class="button button--primary" type="submit" :disabled="loading" :aria-busy="loading"><Send :size="16" aria-hidden="true" />{{ loading ? '验判中' : '提交验判' }}</button>
    </div>
    <p id="flag-help" class="field-help" :class="{ 'field-error': error }" aria-live="polite">{{ error || (isDemo ? '演示可提交 flag{t02-web-r24}，重复提交可查看去重结果。' : '请确认 Flag 来源和当前比赛轮次。') }}</p>
    <div v-if="result && resultMeta" class="submission-feedback" :class="`feedback--${resultMeta.tone}`" role="status">
      <StatusTag :label="resultMeta.label" :tone="resultMeta.tone" />
      <template v-if="accepted"><strong>本队 {{ signed(result.attacker_delta) }} 分</strong><span>当前 {{ result.attacker_score }} 分，对方 {{ signed(result.victim_delta) }} 分</span></template>
      <span v-else>本次提交不产生分数变化。</span>
    </div>

    <el-dialog v-model="feedbackOpen" :title="accepted ? 'Flag 提交成功' : 'Flag 提交失败'" width="min(460px, 92vw)" class="flag-feedback-dialog" append-to-body>
      <div v-if="result && resultMeta" class="flag-feedback" :class="`flag-feedback--${resultMeta.tone}`">
        <div class="flag-feedback__icon"><CircleCheck v-if="accepted" :size="30" aria-hidden="true" /><CircleX v-else :size="30" aria-hidden="true" /></div>
        <h2>{{ accepted ? 'Flag 正确' : resultMeta.label }}</h2>
        <p v-if="accepted">有效攻击成功，本队获得 {{ signed(result.attacker_delta) }} 分。</p>
        <p v-else>{{ failureReason }}</p>
        <dl v-if="accepted" class="flag-feedback__stats">
          <div><dt>本队得分</dt><dd>{{ signed(result.attacker_delta) }}</dd></div>
          <div><dt>对方变化</dt><dd>{{ signed(result.victim_delta) }}</dd></div>
          <div><dt>本队当前总分</dt><dd>{{ result.attacker_score }}</dd></div>
        </dl>
        <p v-else class="flag-feedback__hint">本次提交不产生分数变化。</p>
        <button class="button button--primary" type="button" @click="feedbackOpen = false">知道了</button>
      </div>
    </el-dialog>
  </form>
</template>

<style scoped>
.flag-feedback { display: grid; justify-items: center; gap: var(--space-sm); padding: var(--space-sm) 0 var(--space-xs); text-align: center; }
.flag-feedback__icon { display: grid; place-items: center; width: 56px; height: 56px; border-radius: 50%; background: var(--color-success-soft); color: var(--color-success); }
.flag-feedback--danger .flag-feedback__icon { background: var(--color-danger-soft); color: var(--color-error); }
.flag-feedback--warning .flag-feedback__icon { background: var(--color-warning-soft); color: var(--color-warning-ink); }
.flag-feedback--neutral .flag-feedback__icon { background: var(--color-paper-2); color: var(--color-muted); }
.flag-feedback h2 { color: var(--color-ink); font-size: var(--text-xl); }
.flag-feedback p { max-width: 34ch; color: var(--color-muted); font-size: var(--text-sm); }
.flag-feedback__stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); width: 100%; margin: var(--space-sm) 0; padding: var(--space-sm) 0; border-top: var(--rule-hair) solid var(--color-rule); border-bottom: var(--rule-hair) solid var(--color-rule); }
.flag-feedback__stats dt { color: var(--color-muted); font-size: var(--text-xs); }
.flag-feedback__stats dd { margin: var(--space-2xs) 0 0; color: var(--color-ink); font-size: var(--text-lg); font-weight: 800; }
.flag-feedback__hint { margin-top: var(--space-xs); }
.flag-feedback .button { min-width: 140px; margin-top: var(--space-xs); }
</style>
