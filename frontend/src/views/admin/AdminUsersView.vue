<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Plus, RefreshCw, Trash2 } from '@lucide/vue'
import { api } from '@/api/client'
import type { Role, User } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatDate } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'

const { data, loading, loaded, error, load } = useAsyncData(async () => ({ users: await api.adminUsers(), teams: await api.adminTeams() }), { users: [], teams: [] })
const query = ref('')
const dialogOpen = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const actionError = ref('')
const actionMessage = ref('')
const form = reactive({ username: '', password: '', role: 'PLAYER' as Role, team_id: null as string | null, status: 'ACTIVE' as 'ACTIVE' | 'DISABLED' })
const rows = computed(() => data.value.users.filter(user => user.username.includes(query.value.trim()) || user.team_name?.includes(query.value.trim())))
function openCreate() { editingId.value = null; Object.assign(form, { username: '', password: '', role: 'PLAYER', team_id: null, status: 'ACTIVE' }); dialogOpen.value = true }
function openEdit(user: User) { editingId.value = user.id; Object.assign(form, { username: user.username, password: '', role: user.role, team_id: user.team_id, status: user.status }); dialogOpen.value = true }
async function save() {
  actionError.value = ''
  if (!form.username.trim() || (!editingId.value && !form.password)) { actionError.value = '请填写用户名和初始密码。'; return }
  if (form.role === 'PLAYER' && !form.team_id) { actionError.value = '选手必须加入一支队伍。'; return }
  saving.value = true
  try {
    if (editingId.value) await api.updateUser(editingId.value, { role: form.role, team_id: form.role === 'ADMIN' ? null : form.team_id, status: form.status, ...(form.password ? { password: form.password } : {}) })
    else await api.createUser({ username: form.username.trim(), password: form.password, role: form.role, team_id: form.role === 'ADMIN' ? null : form.team_id })
    dialogOpen.value = false; actionMessage.value = '账号信息已保存。'; await load()
  } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '保存失败。' } finally { saving.value = false }
}
async function resetPassword(user: User) {
  try {
    const { value } = await ElMessageBox.prompt(`为 ${user.username} 设置新密码。`, '重置密码', { inputType: 'password', inputPlaceholder: '至少 8 位', inputValidator: value => String(value).length >= 8 || '密码至少 8 位', confirmButtonText: '确认重置', cancelButtonText: '取消' })
    await api.updateUser(user.id, { password: value }); actionMessage.value = `${user.username} 的密码已重置。`
  } catch (cause) { if (cause !== 'cancel' && cause !== 'close') actionError.value = cause instanceof Error ? cause.message : '密码重置失败。' }
}
async function removeUser(user: User) {
  actionError.value = ''
  try {
    await ElMessageBox.confirm(`确认删除选手「${user.username}」？删除后账号不可恢复；已有提交记录的选手不能删除，请改用禁用。`, '删除选手', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
    await api.deleteUser(user.id)
    actionMessage.value = `选手 ${user.username} 已删除。`
    await load()
  } catch (cause) {
    if (cause !== 'cancel' && cause !== 'close') actionError.value = cause instanceof Error ? cause.message : '删除失败，请重试。'
  }
}
onMounted(load)
</script>

<template>
  <PageHeader title="选手管理" description="平台仅设选手和管理员两种角色，队伍调整只能由管理员完成。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新</button><button class="button button--primary" type="button" @click="openCreate"><Plus :size="16" aria-hidden="true" />新建账号</button></template>
  </PageHeader>
  <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p><p v-if="actionMessage" class="inline-success" role="status">{{ actionMessage }}</p>
  <div class="table-toolbar"><label for="user-search">搜索账号</label><input id="user-search" v-model="query" class="input toolbar-input" type="search" placeholder="用户名或队伍" /></div>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!rows.length" empty-text="没有匹配的账号。" @retry="load"><div class="table-scroll" tabindex="0" role="region" aria-label="用户列表，窄屏可横向滚动"><table v-responsive-table class="data-table"><thead><tr><th>用户名</th><th>角色</th><th>所属队伍</th><th>状态</th><th>最近登录</th><th class="action-cell">操作</th></tr></thead><tbody><tr v-for="user in rows" :key="user.id"><td><strong>{{ user.username }}</strong></td><td>{{ user.role === 'ADMIN' ? '管理员' : '选手' }}</td><td>{{ user.team_name || '不加入队伍' }}</td><td><StatusTag :label="user.status === 'ACTIVE' ? '正常' : '已禁用'" :tone="user.status === 'ACTIVE' ? 'success' : 'neutral'" /></td><td>{{ formatDate(user.last_login_at) }}</td><td class="action-cell"><div class="table-actions"><button class="button button--text" type="button" @click="openEdit(user)">编辑</button><button class="button button--text" type="button" @click="resetPassword(user)">重置密码</button><button v-if="user.role === 'PLAYER'" class="button button--text" type="button" @click="removeUser(user)"><Trash2 :size="15" aria-hidden="true" />删除</button></div></td></tr></tbody></table></div></DataState>
  <el-dialog v-model="dialogOpen" :title="editingId ? '编辑账号' : '新建账号'" width="min(520px, 92vw)"><form class="dialog-form" @submit.prevent="save"><div class="form-field"><label for="account-name">用户名</label><input id="account-name" v-model="form.username" class="input" type="text" autocomplete="off" :disabled="!!editingId" required /></div><div class="form-field"><label for="account-password">{{ editingId ? '新密码（留空则不修改）' : '初始密码' }}</label><input id="account-password" v-model="form.password" class="input" type="password" autocomplete="new-password" :required="!editingId" /></div><div class="form-grid"><div class="form-field"><label for="account-role">角色</label><select id="account-role" v-model="form.role" class="input"><option value="PLAYER">选手</option><option value="ADMIN">管理员</option></select></div><div class="form-field"><label for="account-status">状态</label><select id="account-status" v-model="form.status" class="input"><option value="ACTIVE">正常</option><option value="DISABLED">禁用</option></select></div></div><div v-if="form.role === 'PLAYER'" class="form-field"><label for="account-team">所属队伍</label><select id="account-team" v-model="form.team_id" class="input" required><option :value="null" disabled>请选择队伍</option><option v-for="team in data.teams" :key="team.id" :value="team.id" :disabled="team.member_count >= 4 && team.id !== form.team_id">{{ team.name }}（{{ team.member_count }} / 4）</option></select></div><div class="dialog-actions"><button class="button button--secondary" type="button" @click="dialogOpen = false">取消</button><button class="button button--primary" type="submit" :disabled="saving">{{ saving ? '保存中' : '保存账号' }}</button></div></form></el-dialog>
</template>
