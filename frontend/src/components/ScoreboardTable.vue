<script setup lang="ts">
import type { ScoreboardRow } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { formatDate } from '@/utils/format'
import { targetStatus } from '@/utils/format'

defineProps<{ rows: ScoreboardRow[]; compact?: boolean }>()
const auth = useAuthStore()
</script>

<template>
  <div class="table-scroll" tabindex="0" role="region" aria-label="队伍计分表，窄屏可横向滚动">
    <table v-responsive-table class="data-table scoreboard-table">
      <thead><tr><th>排名</th><th>队伍</th><th class="num">总分</th><th class="num">有效攻击</th><th class="num">被攻击</th><th>服务状态</th><th v-if="!compact">最后得分</th></tr></thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id" :class="{ 'is-own-team': auth.user?.team_id === row.id }">
          <td class="rank-cell"><span>{{ String(row.rank).padStart(2, '0') }}</span></td>
          <td><strong>{{ row.name }}</strong><span v-if="auth.user?.team_id === row.id" class="own-label">本队</span><small class="cell-subtitle">队伍 {{ String(row.team_no).padStart(2, '0') }}</small><small class="mobile-team-stats">攻击 {{ row.attack_count }} / 被攻击 {{ row.breached_count }}</small></td>
          <td class="num score-cell">{{ row.current_score }}</td>
          <td class="num">{{ row.attack_count }}</td>
          <td class="num">{{ row.breached_count }}</td>
          <td><div class="service-cells"><span v-for="service in row.services" :key="service.service_code" class="service-state" :class="`text-${targetStatus[service.status].tone}`" :title="`${service.service_name}：${targetStatus[service.status].label}`">{{ service.service_code }}<span class="visually-hidden">{{ targetStatus[service.status].label }}</span></span></div></td>
          <td v-if="!compact" class="muted-cell">{{ formatDate(row.last_scored_at) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  <p v-if="!rows.length" class="table-note">比赛初始化后，这里会显示队伍排名。</p>
</template>
