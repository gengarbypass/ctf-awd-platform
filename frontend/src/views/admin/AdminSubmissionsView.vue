<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, Scale } from '@lucide/vue'
import { api } from '@/api/client'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatDate, signed, submissionResult } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'

const route = useRoute()
const router = useRouter()
const { data, loading, loaded, error, load } = useAsyncData(async () => ({ submissions: await api.adminSubmissions(), ledger: await api.adminLedger(), teams: await api.adminTeams() }), { submissions: [], ledger: [], teams: [] })
const tab = computed(() => String(route.query.tab || 'submissions'))
const resultFilter = ref('ALL')
const rows = computed(() => data.value.submissions.filter(item => resultFilter.value === 'ALL' || item.result === resultFilter.value))
const adjustOpen = ref(false)
const saving = ref(false)
const actionError = ref('')
const actionMessage = ref('')
const adjust = reactive({ team_id: '', delta: 0, reason: '' })
function setTab(value: string) { router.replace({ query: { tab: value } }) }
async function saveAdjustment() {
  actionError.value = ''
  if (!adjust.team_id || !adjust.delta || !adjust.reason.trim()) { actionError.value = '请选择队伍、填写非零分值和改分原因。'; return }
  saving.value = true
  try { await api.adjustScore(adjust.team_id, Number(adjust.delta), adjust.reason.trim()); adjustOpen.value = false; actionMessage.value = '人工改分已写入独立流水和审计日志。'; Object.assign(adjust, { team_id: '', delta: 0, reason: '' }); await load() } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '改分失败。' } finally { saving.value = false }
}
async function exportScores() {
  const blob = await api.exportScores()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = `ctf-awd-scores-${new Date().toISOString().slice(0, 10)}.csv`; anchor.click(); URL.revokeObjectURL(url)
  actionMessage.value = '成绩与队伍汇总已导出。'
}
onMounted(load)
</script>

<template>
  <PageHeader title="提交与流水" description="验判结果、双方分数变化和人工改分均可追溯，流水是成绩核算依据。">
    <template #actions><button class="button button--secondary" type="button" @click="exportScores"><Download :size="16" aria-hidden="true" />导出成绩</button><button class="button button--primary" type="button" @click="adjustOpen = true"><Scale :size="16" aria-hidden="true" />人工改分</button></template>
  </PageHeader>
  <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p><p v-if="actionMessage" class="inline-success" role="status">{{ actionMessage }}</p>
  <div class="view-tabs" role="tablist" aria-label="提交与计分流水"><button type="button" role="tab" :aria-selected="tab === 'submissions'" :class="{ 'is-active': tab === 'submissions' }" @click="setTab('submissions')">Flag 提交</button><button type="button" role="tab" :aria-selected="tab === 'ledger'" :class="{ 'is-active': tab === 'ledger' }" @click="setTab('ledger')">计分流水</button></div>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="tab === 'submissions' ? !rows.length : !data.ledger.length" empty-text="当前没有相关记录。" @retry="load">
    <template v-if="tab === 'submissions'"><div class="table-toolbar"><label for="admin-result-filter">验判结果</label><select id="admin-result-filter" v-model="resultFilter" class="input select-input"><option value="ALL">全部结果</option><option v-for="(meta, key) in submissionResult" :key="key" :value="key">{{ meta.label }}</option></select></div><div class="table-scroll" tabindex="0" role="region" aria-label="全部 Flag 提交，窄屏可横向滚动"><table v-responsive-table class="data-table"><thead><tr><th>时间</th><th>攻击队</th><th>目标队</th><th>服务</th><th>结果</th><th class="num">攻击方</th><th class="num">防守方</th><th>请求 ID</th></tr></thead><tbody><tr v-for="item in rows" :key="item.id"><td>{{ formatDate(item.submitted_at, true) }}</td><td><strong>{{ item.attacker_team_name }}</strong><small v-if="item.username" class="cell-subtitle">{{ item.username }}</small></td><td>{{ item.victim_team_name || '未识别' }}</td><td>{{ item.service_name || '未关联' }}</td><td><StatusTag :label="submissionResult[item.result].label" :tone="submissionResult[item.result].tone" /></td><td class="num text-success">{{ signed(item.attacker_delta) }}</td><td class="num" :class="{ 'text-danger': item.victim_delta < 0 }">{{ signed(item.victim_delta) }}</td><td><code>{{ item.request_id.slice(0, 12) }}</code></td></tr></tbody></table></div></template>
    <div v-else class="table-scroll" tabindex="0" role="region" aria-label="计分流水，窄屏可横向滚动"><table v-responsive-table class="data-table"><thead><tr><th>时间</th><th>队伍</th><th>原因</th><th class="num">分数变化</th><th class="num">变更后总分</th><th>关联提交</th></tr></thead><tbody><tr v-for="entry in data.ledger" :key="entry.id"><td>{{ formatDate(entry.created_at, true) }}</td><td><strong>{{ entry.team_name }}</strong></td><td>{{ entry.reason }}</td><td class="num" :class="entry.delta >= 0 ? 'text-success' : 'text-danger'">{{ signed(entry.delta) }}</td><td class="num score-cell">{{ entry.score_after }}</td><td><code>{{ entry.submission_id?.slice(0, 12) || '人工改分' }}</code></td></tr></tbody></table></div>
  </DataState>
  <el-dialog v-model="adjustOpen" title="人工改分" width="min(500px, 92vw)"><form class="dialog-form" @submit.prevent="saveAdjustment"><div class="form-field"><label for="adjust-team">队伍</label><select id="adjust-team" v-model="adjust.team_id" class="input" required><option value="" disabled>请选择队伍</option><option v-for="team in data.teams" :key="team.id" :value="team.id">{{ team.name }}（当前 {{ team.current_score }} 分）</option></select></div><div class="form-field"><label for="adjust-delta">分数变化</label><input id="adjust-delta" v-model.number="adjust.delta" class="input" type="number" min="-10000" max="10000" required /><p class="field-help">加分填正数，扣分填负数，总分允许低于 0。</p></div><div class="form-field"><label for="adjust-reason">改分原因</label><textarea id="adjust-reason" v-model="adjust.reason" class="input textarea" rows="3" required placeholder="说明事实依据和处理原因" /></div><div class="dialog-actions"><button class="button button--secondary" type="button" @click="adjustOpen = false">取消</button><button class="button button--primary" type="submit" :disabled="saving">{{ saving ? '写入中' : '确认改分' }}</button></div></form></el-dialog>
</template>
