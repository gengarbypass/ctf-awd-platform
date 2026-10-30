<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { FileUp, Plus } from '@lucide/vue'
import { api } from '@/api/client'
import type { Team } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'

const { data, loading, loaded, error, load } = useAsyncData(api.adminTeams, [])
const dialogOpen = ref(false)
const saving = ref(false)
const actionError = ref('')
const actionMessage = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const editingId = ref<string | null>(null)
const form = reactive({ team_no: 1, name: '' })
function openCreate() { editingId.value = null; form.team_no = Math.max(0, ...data.value.map(item => item.team_no)) + 1; form.name = ''; dialogOpen.value = true }
function openEdit(team: Team) { editingId.value = team.id; form.team_no = team.team_no; form.name = team.name; dialogOpen.value = true }
async function save() {
  actionError.value = ''
  if (!form.name.trim() || form.team_no < 1 || form.team_no > 15) { actionError.value = '请输入唯一队名和 1 至 15 的队伍编号。'; return }
  saving.value = true
  try {
    if (editingId.value) await api.updateTeam(editingId.value, { team_no: form.team_no, name: form.name.trim() })
    else await api.createTeam({ team_no: form.team_no, name: form.name.trim() })
    dialogOpen.value = false; actionMessage.value = editingId.value ? '队伍资料已更新。' : '队伍已创建，初始分为 1000 分。'; await load()
  } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '保存失败。' } finally { saving.value = false }
}
async function toggleStatus(team: Team) {
  const disable = team.status === 'ACTIVE'
  if (disable) await ElMessageBox.confirm(`禁用 ${team.name} 后，该队选手将无法登录。确认继续？`, '禁用队伍', { type: 'warning', confirmButtonText: '确认禁用', cancelButtonText: '取消' })
  await api.updateTeam(team.id, { status: disable ? 'DISABLED' : 'ACTIVE' }); actionMessage.value = disable ? '队伍已禁用。' : '队伍已恢复。'; await load()
}
async function resetScore(team: Team) {
  await ElMessageBox.confirm(`将 ${team.name} 的总分重置为 1000，并清零攻击与被攻击次数。该操作会保留审计记录。`, '初始化队伍分数', { type: 'warning', confirmButtonText: '确认初始化', cancelButtonText: '取消' })
  await api.updateTeam(team.id, { reset_score: true }); actionMessage.value = `${team.name} 已恢复初始分。`; await load()
}
async function importCsv(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  actionError.value = ''; actionMessage.value = ''
  try {
    const text = await file.text()
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean)
    const records = lines[0]?.includes('team_no') || lines[0]?.includes('队伍编号') ? lines.slice(1) : lines
    for (const line of records) {
      const [teamNo, name] = line.split(',').map(value => value.trim())
      if (!Number(teamNo) || !name) throw new Error('CSV 格式应为 team_no,name。')
      await api.createTeam({ team_no: Number(teamNo), name })
    }
    actionMessage.value = `已导入 ${records.length} 支队伍。`; await load()
  } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '导入失败，请检查 CSV。' } finally { input.value = '' }
}
onMounted(load)
</script>

<template>
  <PageHeader title="队伍管理" description="最多 15 支队伍，每队 3 至 4 人；队伍编号和名称保持唯一。">
    <template #actions><input ref="fileInput" class="visually-hidden" type="file" accept=".csv,text/csv" aria-label="选择队伍 CSV" @change="importCsv" /><button class="button button--secondary" type="button" @click="fileInput?.click()"><FileUp :size="16" aria-hidden="true" />导入 CSV</button><button class="button button--primary" type="button" @click="openCreate"><Plus :size="16" aria-hidden="true" />新建队伍</button></template>
  </PageHeader>
  <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p><p v-if="actionMessage" class="inline-success" role="status">{{ actionMessage }}</p>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!data.length" empty-text="尚未创建队伍。" @retry="load"><template #empty-action><button class="button button--primary" type="button" @click="openCreate">新建队伍</button></template>
    <div class="table-scroll" tabindex="0" role="region" aria-label="队伍列表，窄屏可横向滚动"><table v-responsive-table class="data-table"><thead><tr><th>编号</th><th>队伍名称</th><th>邀请码</th><th class="num">成员</th><th class="num">当前总分</th><th class="num">攻击 / 被攻击</th><th>状态</th><th class="action-cell">操作</th></tr></thead><tbody><tr v-for="team in data" :key="team.id"><td>{{ String(team.team_no).padStart(2, '0') }}</td><td><strong>{{ team.name }}</strong></td><td><code>{{ team.invite_code }}</code></td><td class="num">{{ team.member_count }} / 4</td><td class="num score-cell">{{ team.current_score }}</td><td class="num">{{ team.attack_count }} / {{ team.breached_count }}</td><td><StatusTag :label="team.status === 'ACTIVE' ? '正常' : '已禁用'" :tone="team.status === 'ACTIVE' ? 'success' : 'neutral'" /></td><td class="action-cell"><div class="table-actions"><button class="button button--text" type="button" @click="openEdit(team)">编辑</button><button class="button button--text" type="button" @click="resetScore(team)">初始化分数</button><button class="button button--text" type="button" @click="toggleStatus(team)">{{ team.status === 'ACTIVE' ? '禁用' : '恢复' }}</button></div></td></tr></tbody></table></div>
  </DataState>
  <el-dialog v-model="dialogOpen" :title="editingId ? '编辑队伍' : '新建队伍'" width="min(480px, 92vw)"><form class="dialog-form" @submit.prevent="save"><div class="form-field"><label for="team-no">队伍编号</label><input id="team-no" v-model.number="form.team_no" class="input" type="number" min="1" max="15" required /></div><div class="form-field"><label for="team-name">队伍名称</label><input id="team-name" v-model="form.name" class="input" type="text" maxlength="30" required /></div><p class="field-help">新队伍初始分为 1000 分，邀请码由系统自动生成。</p><div class="dialog-actions"><button class="button button--secondary" type="button" @click="dialogOpen = false">取消</button><button class="button button--primary" type="submit" :disabled="saving">{{ saving ? '保存中' : '保存队伍' }}</button></div></form></el-dialog>
</template>
