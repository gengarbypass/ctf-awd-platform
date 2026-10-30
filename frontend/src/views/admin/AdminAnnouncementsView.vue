<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Pin, Plus, RefreshCw } from '@lucide/vue'
import { api } from '@/api/client'
import type { AnnouncementLevel } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import { announcementLevel, formatFullDate } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'

const { data, loading, loaded, error, load } = useAsyncData(api.adminAnnouncements, [])
const dialogOpen = ref(false)
const saving = ref(false)
const actionError = ref('')
const actionMessage = ref('')
const form = reactive({ title: '', content: '', level: 'INFO' as AnnouncementLevel, pinned: false })
async function publish() {
  actionError.value = ''
  if (!form.title.trim() || !form.content.trim()) { actionError.value = '请填写公告标题和正文。'; return }
  saving.value = true
  try { await api.createAnnouncement({ title: form.title.trim(), content: form.content.trim(), level: form.level, pinned: form.pinned }); dialogOpen.value = false; Object.assign(form, { title: '', content: '', level: 'INFO', pinned: false }); actionMessage.value = '公告已发布并推送至在线页面。'; await load() } catch (cause) { actionError.value = cause instanceof Error ? cause.message : '发布失败。' } finally { saving.value = false }
}
async function togglePin(id: string, pinned: boolean) { await api.updateAnnouncement(id, { pinned: !pinned }); actionMessage.value = pinned ? '已取消置顶。' : '公告已置顶。'; await load() }
async function withdraw(id: string) { await api.updateAnnouncement(id, { status: 'WITHDRAWN', pinned: false }); actionMessage.value = '公告已撤回，历史记录仍保留。'; await load() }
onMounted(load)
</script>

<template>
  <PageHeader title="公告管理" description="公告用于比赛时间、服务异常和恢复通知，发布后通过实时事件推送。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新</button><button class="button button--primary" type="button" @click="dialogOpen = true"><Plus :size="16" aria-hidden="true" />发布公告</button></template>
  </PageHeader>
  <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p><p v-if="actionMessage" class="inline-success" role="status">{{ actionMessage }}</p>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!data.length" empty-text="尚未发布公告。" @retry="load"><div class="announcement-admin-list"><article v-for="notice in data" :key="notice.id" class="announcement-admin-row"><div class="announcement-admin-row__main"><h2>{{ notice.title }}</h2><div class="announcement-item__meta"><StatusTag :label="announcementLevel[notice.level].label" :tone="announcementLevel[notice.level].tone" /><span v-if="notice.pinned"><Pin :size="14" aria-hidden="true" />已置顶</span><StatusTag :label="notice.status === 'PUBLISHED' ? '已发布' : '已撤回'" :tone="notice.status === 'PUBLISHED' ? 'success' : 'neutral'" /></div><p>{{ notice.content }}</p><time :datetime="notice.published_at">{{ formatFullDate(notice.published_at) }}</time></div><div class="announcement-admin-row__actions"><button class="button button--text" type="button" :disabled="notice.status === 'WITHDRAWN'" @click="togglePin(notice.id, notice.pinned)">{{ notice.pinned ? '取消置顶' : '置顶' }}</button><button v-if="notice.status === 'PUBLISHED'" class="button button--text" type="button" @click="withdraw(notice.id)">撤回</button></div></article></div></DataState>
  <el-dialog v-model="dialogOpen" title="发布公告" width="min(600px, 92vw)"><form class="dialog-form" @submit.prevent="publish"><div class="form-field"><label for="notice-title">公告标题</label><input id="notice-title" v-model="form.title" class="input" type="text" maxlength="80" required /></div><div class="form-field"><label for="notice-content">公告正文</label><textarea id="notice-content" v-model="form.content" class="input textarea" rows="5" maxlength="1000" required /></div><div class="form-field"><label for="notice-level">公告级别</label><select id="notice-level" v-model="form.level" class="input"><option value="INFO">通知</option><option value="WARNING">注意</option><option value="CRITICAL">重要</option></select></div><label class="checkbox-field"><input v-model="form.pinned" type="checkbox" />置顶显示</label><div class="dialog-actions"><button class="button button--secondary" type="button" @click="dialogOpen = false">取消</button><button class="button button--primary" type="submit" :disabled="saving">{{ saving ? '发布中' : '确认发布' }}</button></div></form></el-dialog>
</template>
