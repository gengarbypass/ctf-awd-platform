<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Boxes, RefreshCw } from '@lucide/vue'
import { api } from '@/api/client'
import type { HealthCheck, Target } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatDate } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import TargetTable from '@/components/TargetTable.vue'
import TerminalDialog from '@/components/TerminalDialog.vue'
import StatusTag from '@/components/StatusTag.vue'

const route = useRoute()
const router = useRouter()
const { data, loading, loaded, error, load } = useAsyncData(api.adminTargets, [])
const actionError = ref('')
const actionMessage = ref('')
const terminalTarget = ref<Target | null>(null)
const healthTarget = ref<Target | null>(null)
const healthRecords = ref<HealthCheck[]>([])
const healthLoading = ref(false)
const teamFilter = computed(() => String(route.query.team || 'ALL'))
const statusFilter = computed(() => String(route.query.status || 'ALL'))
const rows = computed(() => data.value.filter(target => (teamFilter.value === 'ALL' || target.team_id === teamFilter.value) && (statusFilter.value === 'ALL' || target.status === statusFilter.value)))
const teams = computed(() => [...new Map(data.value.map(target => [target.team_id, { id: target.team_id, name: target.team_name }])).values()])
function filterQuery() { router.replace({ query: { ...(teamFilter.value === 'ALL' ? {} : { team: teamFilter.value }), ...(statusFilter.value === 'ALL' ? {} : { status: statusFilter.value }) } }) }
function setTeam(value: string) { router.replace({ query: { ...route.query, team: value === 'ALL' ? undefined : value } }) }
function setStatus(value: string) { router.replace({ query: { ...route.query, status: value === 'ALL' ? undefined : value } }) }
async function initialize() {
  await ElMessageBox.confirm('将按队伍和服务模板补齐缺失靶机，已有实例和成绩不会被重置。确认执行？', '初始化靶机', { type: 'info', confirmButtonText: '开始初始化', cancelButtonText: '取消' })
  try { await api.initializeTargets(); actionMessage.value = '靶机初始化完成，未重复创建已有实例。'; await load() } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '初始化失败。' }
}
async function restart(target: Target) {
  try { await ElMessageBox.confirm(`重启 ${target.team_name} 的 ${target.service_name}，保留原数据卷。`, '确认重启', { type: 'warning', confirmButtonText: '确认重启', cancelButtonText: '取消' }); await api.restartTarget(target.id); await load() } catch (cause) { if (cause !== 'cancel' && cause !== 'close') actionError.value = cause instanceof Error ? cause.message : '重启失败。' }
}
async function stopTarget(target: Target) {
  try {
    await ElMessageBox.confirm(`停止 ${target.team_name} 的 ${target.service_name} 后，该服务将无法被访问和攻击。`, '停止靶机', { type: 'warning', confirmButtonText: '确认停止', cancelButtonText: '取消' })
    await api.stopTarget(target.id); actionMessage.value = '靶机已停止。'; await load()
  } catch (cause) { if (cause !== 'cancel' && cause !== 'close') actionError.value = cause instanceof Error ? cause.message : '停止失败。' }
}
async function startTarget(target: Target) {
  try { await api.startTarget(target.id); actionMessage.value = '靶机启动中，健康检查通过后恢复运行。'; await load() } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '启动失败。' }
}
async function showHealth(target: Target) {
  healthTarget.value = target
  healthLoading.value = true
  healthRecords.value = []
  try { healthRecords.value = await api.healthRecords(target.id) } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '健康记录读取失败。' } finally { healthLoading.value = false }
}
onMounted(load)
</script>

<template>
  <PageHeader title="靶机管理" description="每队每种服务仅一个实例，初始化操作幂等且不会重置已有成绩。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新状态</button><button class="button button--primary" type="button" @click="initialize"><Boxes :size="16" aria-hidden="true" />初始化缺失靶机</button></template>
  </PageHeader>
  <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p><p v-if="actionMessage" class="inline-success" role="status">{{ actionMessage }}</p>
  <dl class="stat-row"><div><dt>靶机实例</dt><dd>{{ data.length }}</dd></div><div><dt>运行正常</dt><dd>{{ data.filter(item => item.status === 'RUNNING').length }}</dd></div><div><dt>恢复中</dt><dd>{{ data.filter(item => item.status === 'RESTARTING').length }}</dd></div><div><dt>异常或人工处理</dt><dd>{{ data.filter(item => ['UNHEALTHY', 'MANUAL_INTERVENTION'].includes(item.status)).length }}</dd></div></dl>
  <div class="table-toolbar table-toolbar--filters"><div><label for="target-team-filter">队伍</label><select id="target-team-filter" class="input select-input" :value="teamFilter" @change="setTeam(($event.target as HTMLSelectElement).value)"><option value="ALL">全部队伍</option><option v-for="team in teams" :key="team.id" :value="team.id">{{ team.name }}</option></select></div><div><label for="target-status-filter">状态</label><select id="target-status-filter" class="input select-input" :value="statusFilter" @change="setStatus(($event.target as HTMLSelectElement).value)"><option value="ALL">全部状态</option><option value="RUNNING">运行正常</option><option value="UNHEALTHY">服务异常</option><option value="RESTARTING">恢复中</option><option value="MANUAL_INTERVENTION">待人工处理</option><option value="STOPPED">已停止</option></select></div><button class="button button--text" type="button" @click="filterQuery">应用筛选</button></div>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!rows.length" empty-text="当前筛选条件下没有靶机实例。" @retry="load"><TargetTable :targets="rows" show-team admin-mode @restart="restart" @terminal="terminalTarget = $event" @stop="stopTarget" @start="startTarget" @health="showHealth" /></DataState>
  <TerminalDialog :target="terminalTarget" :open="!!terminalTarget" @close="terminalTarget = null" />
  <el-dialog :model-value="!!healthTarget" :title="healthTarget ? `${healthTarget.team_name} / ${healthTarget.service_name} 健康记录` : '健康记录'" width="min(680px, 92vw)" @close="healthTarget = null">
    <div class="section-heading"><div><h2>最近检查</h2><p>连续两次失败才会判定异常；健康状态不参与加减分。</p></div></div>
    <DataState :loading="healthLoading" :loaded="!!healthRecords.length" :error="''" :empty="!healthRecords.length" empty-text="该靶机还没有健康检查记录。" @retry="() => healthTarget && showHealth(healthTarget)">
      <div class="table-scroll" tabindex="0" role="region" aria-label="健康检查记录，窄屏可横向滚动"><table v-responsive-table class="data-table"><thead><tr><th>检查时间</th><th>结果</th><th class="num">耗时（ms）</th><th>错误信息</th></tr></thead><tbody><tr v-for="record in healthRecords" :key="record.id"><td>{{ formatDate(record.checked_at, true) }}</td><td><StatusTag :label="record.status === 'HEALTHY' ? '正常' : '异常'" :tone="record.status === 'HEALTHY' ? 'success' : 'danger'" /></td><td class="num">{{ record.duration_ms }}</td><td class="muted-cell">{{ record.error || '无' }}</td></tr></tbody></table></div>
    </DataState>
  </el-dialog>
</template>
