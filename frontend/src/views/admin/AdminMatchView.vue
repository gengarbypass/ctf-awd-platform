<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Flag, LockKeyhole, Pause, Play, Square } from '@lucide/vue'
import { api } from '@/api/client'
import type { Match, MatchStatus } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatFullDate, matchStatus } from '@/utils/format'
import { useMatchStore } from '@/stores/match'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'

const { data, loading, loaded, error, load } = useAsyncData(api.match, null as Match | null)
const shellMatch = useMatchStore()
const config = reactive({ ends_at: '', round_seconds: 300, grace_seconds: 30 })
const createForm = reactive({ name: '师市行内部对抗', starts_at: '', ends_at: '' })
const actionError = ref('')
const actionMessage = ref('')
const busy = ref('')
const stateFlow: { key: MatchStatus; label: string }[] = [{ key: 'DRAFT', label: '草稿' }, { key: 'READY', label: '待开始' }, { key: 'RUNNING', label: '进行中' }, { key: 'PAUSED', label: '已暂停' }, { key: 'FINISHED', label: '已结束' }]
const canEdit = computed(() => data.value?.status === 'DRAFT')
function toLocalInput(value: string) { const date = new Date(value); const offset = date.getTimezoneOffset() * 60_000; return new Date(date.getTime() - offset).toISOString().slice(0, 16) }
function syncConfig() { if (!data.value) return; config.ends_at = toLocalInput(data.value.ends_at); config.round_seconds = data.value.round_seconds; config.grace_seconds = data.value.grace_seconds }
async function reload() { await load(); syncConfig() }
async function action(name: 'ready' | 'start' | 'pause' | 'resume' | 'finish') {
  actionError.value = ''; actionMessage.value = ''
  if (name === 'finish') await ElMessageBox.confirm('结束比赛后将停止 Flag 轮换和提交，且不能直接恢复。确认结束？', '结束比赛', { type: 'warning', confirmButtonText: '确认结束', cancelButtonText: '取消' })
  busy.value = name
  try { data.value = name === 'ready' ? await api.readyMatch() : await api.matchAction(name); actionMessage.value = `比赛状态已更新为${matchStatus[data.value.status].label}。`; await shellMatch.load() } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '操作失败。' } finally { busy.value = '' }
}
async function freeze() { if (!data.value) return; data.value = await api.freezeMatch(!data.value.score_frozen); actionMessage.value = data.value.score_frozen ? '前台计分板已冻结，后台继续计分。' : '计分板已解除冻结。'; await shellMatch.load() }
async function saveConfig() {
  actionError.value = ''
  if (!config.ends_at || config.round_seconds < 180 || config.round_seconds > 600 || config.grace_seconds < 0 || config.grace_seconds > 60) { actionError.value = '轮换周期应为 180 至 600 秒，宽限期应为 0 至 60 秒。'; return }
  busy.value = 'config'
  try { data.value = await api.updateMatch({ ends_at: new Date(config.ends_at).toISOString(), round_seconds: config.round_seconds, grace_seconds: config.grace_seconds }); actionMessage.value = '比赛参数已保存。'; await shellMatch.load() } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '保存失败。' } finally { busy.value = '' }
}
async function createMatch() {
  actionError.value = ''
  if (!createForm.name.trim() || !createForm.starts_at || !createForm.ends_at) { actionError.value = '请填写比赛名称、开始时间和结束时间。'; return }
  if (new Date(createForm.ends_at) <= new Date(createForm.starts_at)) { actionError.value = '结束时间必须晚于开始时间。'; return }
  busy.value = 'create'
  try {
    data.value = await api.createMatch({ name: createForm.name.trim(), starts_at: new Date(createForm.starts_at).toISOString(), ends_at: new Date(createForm.ends_at).toISOString(), round_seconds: 300, grace_seconds: 30 })
    syncConfig(); actionMessage.value = '比赛已创建，请初始化靶机并完成赛前检查。'; await shellMatch.load()
  } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '创建比赛失败。' } finally { busy.value = '' }
}
onMounted(reload)
</script>

<template>
  <PageHeader title="比赛控制" description="暂停会同步停止比赛计时、Flag 轮换和提交；页面与终端仍可查看。" />
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!data" empty-text="尚未创建比赛。先设置本场时间，再初始化队伍与靶机。" @retry="reload">
    <template #empty-action><form class="create-match-form" @submit.prevent="createMatch"><div class="form-field"><label for="create-match-name">比赛名称</label><input id="create-match-name" v-model="createForm.name" class="input" type="text" required /></div><div class="form-grid"><div class="form-field"><label for="create-match-start">开始时间</label><input id="create-match-start" v-model="createForm.starts_at" class="input" type="datetime-local" required /></div><div class="form-field"><label for="create-match-end">结束时间</label><input id="create-match-end" v-model="createForm.ends_at" class="input" type="datetime-local" required /></div></div><p class="field-help">默认每场 4 小时，Flag 每 300 秒轮换，上一周期宽限 30 秒。</p><button class="button button--primary" type="submit" :disabled="busy === 'create'">{{ busy === 'create' ? '创建中' : '创建比赛' }}</button></form></template>
    <template v-if="data">
      <section class="match-control-panel"><div class="match-control-panel__summary"><StatusTag :label="matchStatus[data.status].label" :tone="matchStatus[data.status].tone" /><h2>{{ data.name }}</h2><dl><div><dt>开始时间</dt><dd>{{ formatFullDate(data.starts_at) }}</dd></div><div><dt>结束时间</dt><dd>{{ formatFullDate(data.ends_at) }}</dd></div><div><dt>当前轮次</dt><dd>第 {{ data.current_round }} 轮</dd></div></dl></div><div class="match-control-panel__actions"><button v-if="data.status === 'DRAFT'" class="button button--primary" type="button" :disabled="!!busy" @click="action('ready')"><Flag :size="16" aria-hidden="true" />完成赛前检查</button><button v-if="data.status === 'READY'" class="button button--primary" type="button" :disabled="!!busy" @click="action('start')"><Play :size="16" aria-hidden="true" />开始比赛</button><button v-if="data.status === 'RUNNING'" class="button button--primary" type="button" :disabled="!!busy" @click="action('pause')"><Pause :size="16" aria-hidden="true" />暂停比赛</button><button v-if="data.status === 'PAUSED'" class="button button--primary" type="button" :disabled="!!busy" @click="action('resume')"><Play :size="16" aria-hidden="true" />恢复比赛</button><button class="button button--secondary" type="button" :disabled="!!busy || !['RUNNING', 'PAUSED'].includes(data.status)" @click="freeze"><LockKeyhole :size="16" aria-hidden="true" />{{ data.score_frozen ? '解除冻结' : '冻结计分板' }}</button><button class="button button--secondary danger-button" type="button" :disabled="!!busy || data.status === 'FINISHED'" @click="action('finish')"><Square :size="15" aria-hidden="true" />结束比赛</button></div></section>
      <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p><p v-if="actionMessage" class="inline-success" role="status">{{ actionMessage }}</p>
      <ol class="match-state-flow" aria-label="比赛状态机"><li v-for="state in stateFlow" :key="state.key" :class="{ 'is-current': data.status === state.key, 'is-finished': data.status === 'FINISHED' && state.key !== 'FINISHED' }"><Flag :size="15" aria-hidden="true" /><span>{{ state.label }}</span></li></ol>
      <div class="match-config-grid"><form class="section-block config-form" @submit.prevent="saveConfig"><div class="section-heading"><div><h2>时间与轮换参数</h2><p>比赛进行中不能修改既有计分参数</p></div></div><div class="form-field"><label for="match-end">结束时间</label><input id="match-end" v-model="config.ends_at" class="input" type="datetime-local" :disabled="!canEdit" /></div><div class="form-grid"><div class="form-field"><label for="round-seconds">轮换周期（秒）</label><input id="round-seconds" v-model.number="config.round_seconds" class="input" type="number" min="180" max="600" step="30" :disabled="!canEdit" /></div><div class="form-field"><label for="grace-seconds">提交宽限（秒）</label><input id="grace-seconds" v-model.number="config.grace_seconds" class="input" type="number" min="0" max="60" :disabled="!canEdit" /></div></div><button class="button button--primary" type="submit" :disabled="!canEdit || busy === 'config'">{{ busy === 'config' ? '保存中' : '保存参数' }}</button><p v-if="!canEdit" class="field-help">仅草稿状态可编辑时间与轮换参数，完成赛前检查后锁定。</p></form><section class="section-block"><div class="section-heading"><div><h2>计分规则</h2><p>正式开赛后锁定，不随健康状态变化</p></div></div><dl class="rules-list"><div><dt>队伍初始分</dt><dd>1000</dd></div><div><dt>有效攻击</dt><dd>攻击队 +100</dd></div><div><dt>被有效攻击</dt><dd>防守队 -50</dd></div><div><dt>重复或本队提交</dt><dd>不计分</dd></div><div><dt>服务健康异常</dt><dd>不计分</dd></div></dl></section></div>
    </template>
  </DataState>
</template>
