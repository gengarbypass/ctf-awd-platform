<script setup lang="ts">
import { onMounted } from 'vue'
import { AlertTriangle, ChevronRight, RefreshCw } from '@lucide/vue'
import { api } from '@/api/client'
import type { AdminOverview } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatDate, matchStatus, submissionResult, targetStatus } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'

const empty: AdminOverview = { match: null, team_count: 0, online_team_count: 0, player_count: 0, healthy_target_count: 0, target_count: 0, abnormal_targets: [], latest_submissions: [] }
const { data, loading, loaded, error, load } = useAsyncData(api.adminOverview, empty)
onMounted(load)
</script>

<template>
  <PageHeader title="运行总览" description="集中查看比赛、异常靶机和最新验判，异常状态不直接改变分数。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新总览</button></template>
  </PageHeader>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="false" @retry="load">
    <section v-if="data.match" class="admin-match-line"><div><StatusTag :label="matchStatus[data.match.status].label" :tone="matchStatus[data.match.status].tone" /><strong>{{ data.match.name }}</strong></div><div><span>当前第 {{ data.match.current_round }} 轮</span><span>{{ data.match.round_seconds }} 秒轮换</span><RouterLink to="/admin/match" class="text-link">比赛控制<ChevronRight :size="15" aria-hidden="true" /></RouterLink></div></section>
    <p v-else class="quiet-empty">尚未创建比赛。请先到 <RouterLink to="/admin/match" class="text-link">比赛控制</RouterLink> 创建比赛并完成赛前检查。</p>
    <dl class="stat-row"><div><dt>在线队伍</dt><dd>{{ data.online_team_count }}<small>/ {{ data.team_count }}</small></dd></div><div><dt>选手账号</dt><dd>{{ data.player_count }}</dd></div><div><dt>正常靶机</dt><dd>{{ data.healthy_target_count }}<small>/ {{ data.target_count }}</small></dd></div><div><dt>异常待处理</dt><dd :class="{ 'text-danger': data.abnormal_targets.length }">{{ data.abnormal_targets.length }}</dd></div></dl>
    <div class="admin-overview-grid">
      <section class="section-block" aria-labelledby="abnormal-title"><div class="section-heading"><div><h2 id="abnormal-title">异常靶机</h2><p>优先处理人工介入与连续检查失败</p></div><RouterLink to="/admin/targets" class="text-link">全部靶机<ChevronRight :size="15" aria-hidden="true" /></RouterLink></div><div v-if="data.abnormal_targets.length" class="issue-list"><div v-for="target in data.abnormal_targets" :key="target.id" class="issue-row"><AlertTriangle :size="18" aria-hidden="true" /><div><strong>{{ target.team_name }} / {{ target.service_name }}</strong><small>{{ target.error || target.container_name }}</small></div><StatusTag :label="targetStatus[target.status].label" :tone="targetStatus[target.status].tone" /></div></div><p v-else class="quiet-empty">全部靶机健康检查正常。</p></section>
      <section class="section-block" aria-labelledby="latest-submissions-title"><div class="section-heading"><div><h2 id="latest-submissions-title">最新提交</h2><p>显示已完成的验判结果</p></div><RouterLink to="/admin/submissions" class="text-link">提交与流水<ChevronRight :size="15" aria-hidden="true" /></RouterLink></div><div class="compact-feed"><div v-for="item in data.latest_submissions" :key="item.id" class="compact-feed__row"><div><strong>{{ item.attacker_team_name }}<template v-if="item.victim_team_name"> → {{ item.victim_team_name }}</template></strong><small>{{ formatDate(item.submitted_at, true) }}<template v-if="item.service_name"> / {{ item.service_name }}</template></small></div><StatusTag :label="submissionResult[item.result].label" :tone="submissionResult[item.result].tone" /></div></div></section>
    </div>
  </DataState>
</template>
