<script setup lang="ts">
import { ref } from 'vue'
import { Activity, Check, Copy, Play, RotateCw, Square, SquareTerminal } from '@lucide/vue'
import type { Target } from '@/api/types'
import { formatDate, targetStatus } from '@/utils/format'
import StatusTag from './StatusTag.vue'

defineProps<{ targets: Target[]; showTeam?: boolean; adminMode?: boolean }>()
const emit = defineEmits<{ restart: [target: Target]; terminal: [target: Target]; start: [target: Target]; stop: [target: Target]; health: [target: Target] }>()
const copiedId = ref('')
const host = location.hostname
async function copyAddress(target: Target) {
  await navigator.clipboard.writeText(`${location.hostname}:${target.public_port}`)
  copiedId.value = target.id
  window.setTimeout(() => { if (copiedId.value === target.id) copiedId.value = '' }, 1600)
}
</script>

<template>
  <div class="table-scroll" tabindex="0" role="region" aria-label="靶机服务列表，窄屏可横向滚动">
    <table v-responsive-table class="data-table target-table">
      <thead><tr><th v-if="showTeam">队伍</th><th>服务</th><th>比赛入口</th><th>容器</th><th>状态</th><th>最近检查</th><th class="action-cell">操作</th></tr></thead>
      <tbody>
        <tr v-for="target in targets" :key="target.id">
          <td v-if="showTeam"><strong>{{ target.team_name }}</strong><small class="cell-subtitle">队伍 {{ String(target.team_no).padStart(2, '0') }}</small></td>
          <td><strong>{{ target.service_name }}</strong><small class="cell-subtitle">{{ target.protocol }}:{{ target.internal_port }}</small></td>
          <td><div class="copy-value"><code>{{ host }}:{{ target.public_port }}</code><button class="icon-button" type="button" :aria-label="`复制 ${target.service_name} 比赛入口`" @click="copyAddress(target)"><Check v-if="copiedId === target.id" :size="15" aria-hidden="true" /><Copy v-else :size="15" aria-hidden="true" /></button></div></td>
          <td><code>{{ target.container_name }}</code></td>
          <td><StatusTag :label="targetStatus[target.status].label" :tone="targetStatus[target.status].tone" /><small v-if="target.error" class="cell-subtitle text-danger">{{ target.error }}</small></td>
          <td class="muted-cell">{{ formatDate(target.last_checked_at, true) }}</td>
          <td class="action-cell"><div class="table-actions"><button class="button button--text" type="button" @click="emit('terminal', target)"><SquareTerminal :size="16" aria-hidden="true" />终端</button><button class="button button--text" type="button" @click="emit('restart', target)"><RotateCw :size="16" aria-hidden="true" />重启</button><template v-if="adminMode"><button class="button button--text" type="button" @click="emit('health', target)"><Activity :size="16" aria-hidden="true" />健康记录</button><button v-if="target.status === 'STOPPED'" class="button button--text" type="button" @click="emit('start', target)"><Play :size="16" aria-hidden="true" />启动</button><button v-else class="button button--text" type="button" @click="emit('stop', target)"><Square :size="15" aria-hidden="true" />停止</button></template></div></td>
        </tr>
      </tbody>
    </table>
  </div>
  <p class="table-scroll-hint">服务信息可横向查看，操作列保持可见。</p>
</template>
