<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { LockKeyhole, RefreshCw, Search } from '@lucide/vue'
import { api, createEventSource } from '@/api/client'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatDate } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import ScoreboardTable from '@/components/ScoreboardTable.vue'

const { data, loading, loaded, error, load } = useAsyncData(api.scoreboard, { version: 0, generated_at: '', frozen: false, rows: [] })
const connected = ref(false)
const query = ref('')
const rows = computed(() => data.value.rows.filter(row => row.name.toLowerCase().includes(query.value.trim().toLowerCase()) || String(row.team_no).includes(query.value.trim())))
let disconnect: (() => void) | undefined
onMounted(async () => { await load(); disconnect = createEventSource(load, value => { connected.value = value }) })
onBeforeUnmount(() => disconnect?.())
</script>

<template>
  <PageHeader title="实时计分板" description="有效攻击计分后，最迟 5 秒更新；服务健康不额外加减分。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新快照</button></template>
  </PageHeader>
  <div v-if="data.frozen" class="inline-banner inline-banner--warning"><LockKeyhole :size="18" aria-hidden="true" /><div><strong>计分板已冻结</strong><p>当前展示冻结时刻快照，后台仍正常验判并保存计分流水。</p></div></div>
  <div class="board-toolbar"><div class="search-field"><Search :size="16" aria-hidden="true" /><input v-model="query" class="input" type="search" aria-label="搜索队伍" placeholder="搜索队名或编号" /></div><div class="board-meta"><span :class="connected ? 'text-success' : 'text-warning'">{{ connected ? '实时连接正常' : '正在重新连接' }}</span><span>快照 {{ formatDate(data.generated_at, true) }}</span><span>版本 {{ data.version }}</span></div></div>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!rows.length" :empty-text="query ? '没有匹配的队伍，请更换搜索条件。' : '比赛初始化后显示队伍排名。'" @retry="load"><ScoreboardTable :rows="rows" /><p v-if="error" class="inline-error" role="alert">{{ error }}</p></DataState>
  <div class="ranking-rules"><strong>同分排名</strong><span>有效攻击次数</span><span>服务异常累计时长</span><span>最后有效得分时间</span><span>队伍编号</span></div>
</template>
