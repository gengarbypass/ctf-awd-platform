<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ChevronRight, MonitorCog, Trophy } from '@lucide/vue'
import { api } from '@/api/client'
import { useAsyncData } from '@/composables/useAsyncData'
import { useAuthStore } from '@/stores/auth'
import { useMatchStore } from '@/stores/match'
import { announcementLevel, formatDate, formatDuration, matchStatus, targetStatus } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'
import FlagSubmitForm from '@/components/FlagSubmitForm.vue'
import ScoreboardTable from '@/components/ScoreboardTable.vue'

const auth = useAuthStore()
const matchStore = useMatchStore()
const { data, loading, loaded, error, load } = useAsyncData(async () => {
  const [scoreboard, targets, notices] = await Promise.all([api.scoreboard(), api.targetsMine(), api.announcements()])
  return { scoreboard, targets, notices }
}, { scoreboard: { version: 0, generated_at: '', frozen: false, rows: [] }, targets: [], notices: [] })
const ownRow = computed(() => data.value.scoreboard.rows.find(row => row.id === auth.user?.team_id))
const healthy = computed(() => data.value.targets.filter(item => item.status === 'RUNNING').length)
onMounted(load)
</script>

<template>
  <PageHeader title="训练首页" :description="`${auth.user?.team_name || '未加入队伍'}，关注轮次变化并及时修复本队服务。`">
    <template #actions><RouterLink class="button button--secondary" to="/scoreboard"><Trophy :size="16" aria-hidden="true" />完整计分板</RouterLink></template>
  </PageHeader>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="false" @retry="load">
    <div class="dashboard-command">
      <section class="score-plate" aria-labelledby="own-score-title">
        <div class="score-plate__head"><div><h2 id="own-score-title">本队当前总分</h2><p>第 {{ ownRow?.rank || '待定' }} 名，共 {{ data.scoreboard.rows.length }} 支队伍</p></div><StatusTag :label="matchStore.statusLabel" :tone="matchStore.match ? matchStatus[matchStore.match.status].tone : 'neutral'" /></div>
        <strong class="score-plate__figure num">{{ ownRow?.current_score ?? '待计分' }}</strong>
        <dl class="score-plate__stats"><div><dt>有效攻击</dt><dd>{{ ownRow?.attack_count ?? 0 }}</dd></div><div><dt>被攻击</dt><dd>{{ ownRow?.breached_count ?? 0 }}</dd></div><div><dt>比赛剩余</dt><dd>{{ formatDuration(matchStore.remainingSeconds) }}</dd></div></dl>
      </section>
      <section class="flag-panel" aria-labelledby="flag-panel-title"><h2 id="flag-panel-title" class="visually-hidden">Flag 验判</h2><FlagSubmitForm @accepted="load" /><div class="round-timing"><span>下一轮 Flag</span><strong class="num">{{ formatDuration(matchStore.roundRemainingSeconds) }}</strong><small>轮换周期 {{ matchStore.match?.round_seconds || 300 }} 秒，宽限 {{ matchStore.match?.grace_seconds || 30 }} 秒</small></div></section>
    </div>

    <div class="dashboard-grid">
      <section class="section-block" aria-labelledby="target-summary-title"><div class="section-heading"><div><h2 id="target-summary-title">本队服务</h2><p>{{ healthy }} / {{ data.targets.length }} 个服务运行正常</p></div><RouterLink to="/targets" class="text-link">管理靶机<ChevronRight :size="15" aria-hidden="true" /></RouterLink></div><div class="status-rows"><div v-for="target in data.targets" :key="target.id" class="status-row"><MonitorCog :size="17" aria-hidden="true" /><div><strong>{{ target.service_name }}</strong><small>{{ target.container_name }}</small></div><StatusTag :label="targetStatus[target.status].label" :tone="targetStatus[target.status].tone" /></div></div></section>
      <section class="section-block" aria-labelledby="latest-notice-title"><div class="section-heading"><div><h2 id="latest-notice-title">最新公告</h2><p>比赛变更和服务恢复通知</p></div><RouterLink to="/announcements" class="text-link">全部公告<ChevronRight :size="15" aria-hidden="true" /></RouterLink></div><div class="notice-list"><article v-for="notice in data.notices.slice(0, 3)" :key="notice.id" class="notice-row"><h3>{{ notice.title }}</h3><div class="notice-row__meta"><StatusTag :label="announcementLevel[notice.level].label" :tone="announcementLevel[notice.level].tone" /><time :datetime="notice.published_at">{{ formatDate(notice.published_at) }}</time></div><p>{{ notice.content }}</p></article></div></section>
    </div>
    <section class="section-block score-preview" aria-labelledby="score-preview-title"><div class="section-heading"><div><h2 id="score-preview-title">当前排名</h2><p>按总分、有效攻击和服务异常时长排序</p></div><RouterLink to="/scoreboard" class="text-link">实时计分板<ChevronRight :size="15" aria-hidden="true" /></RouterLink></div><ScoreboardTable :rows="data.scoreboard.rows.slice(0, 5)" compact /></section>
  </DataState>
</template>
