<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Check, Copy, RefreshCw, Search, Swords } from '@lucide/vue'
import { api } from '@/api/client'
import type { OpponentTarget } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatDate, targetStatus } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'

const { data, loading, loaded, error, load } = useAsyncData(api.opponentTargets, [])
const query = ref('')
const copiedId = ref('')
const host = location.hostname
const rows = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return data.value
  return data.value.filter(target =>
    target.team_name.toLowerCase().includes(keyword)
    || String(target.team_no).includes(keyword)
    || target.service_name.toLowerCase().includes(keyword)
    || target.service_code.toLowerCase().includes(keyword),
  )
})
const teamCount = computed(() => new Set(data.value.map(target => target.team_id)).size)
const healthyCount = computed(() => data.value.filter(target => target.status === 'RUNNING').length)

function endpoint(target: OpponentTarget) {
  return `${host}:${target.public_port}`
}

async function copyAddress(target: OpponentTarget) {
  await navigator.clipboard.writeText(endpoint(target))
  copiedId.value = target.id
  window.setTimeout(() => { if (copiedId.value === target.id) copiedId.value = '' }, 1600)
}
onMounted(load)
</script>

<template>
  <PageHeader title="攻击目标" description="查看其他队伍已开放的比赛入口。只允许访问这些地址和端口，不允许访问管理网或宿主机。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新入口</button></template>
  </PageHeader>

  <dl class="stat-row">
    <div><dt>可攻击队伍</dt><dd>{{ teamCount }}</dd></div>
    <div><dt>公开服务入口</dt><dd>{{ data.length }}</dd></div>
    <div><dt>当前运行正常</dt><dd>{{ healthyCount }}</dd></div>
    <div><dt>本队靶机</dt><dd class="stat-link"><RouterLink to="/targets">去我的靶机</RouterLink></dd></div>
  </dl>

  <div class="inline-banner inline-banner--warning"><Swords :size="18" aria-hidden="true" /><div><strong>只打公开比赛端口</strong><p>本页只提供其他队伍的服务地址和公网端口，不提供容器名、管理网关或宿主机信息。禁止扫描平台管理网和其他未开放端口。</p></div></div>

  <div class="board-toolbar">
    <div class="search-field"><Search :size="16" aria-hidden="true" /><input v-model="query" class="input" type="search" aria-label="搜索队伍或服务" placeholder="搜索队伍、编号或服务" /></div>
    <div class="board-meta"><span>共 {{ rows.length }} 个入口</span><span>地址主机：{{ host }}</span></div>
  </div>

  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!rows.length" :empty-text="query ? '没有匹配的攻击目标。' : '其他队伍还没有可攻击的靶机，请联系管理员初始化。'" @retry="load">
    <div class="table-scroll" tabindex="0" role="region" aria-label="其他队伍靶机入口，窄屏可横向滚动">
      <table v-responsive-table class="data-table">
        <thead><tr><th>队伍</th><th>服务</th><th>比赛入口</th><th>协议</th><th>状态</th><th>最近检查</th></tr></thead>
        <tbody>
          <tr v-for="target in rows" :key="target.id">
            <td><strong>{{ target.team_name }}</strong><small class="cell-subtitle">队伍 {{ String(target.team_no).padStart(2, '0') }}</small></td>
            <td><strong>{{ target.service_name }}</strong><small class="cell-subtitle"><code>{{ target.service_code }}</code></small></td>
            <td><div class="copy-value"><code>{{ endpoint(target) }}</code><button class="icon-button" type="button" :aria-label="`复制 ${target.team_name} ${target.service_name} 比赛入口`" @click="copyAddress(target)"><Check v-if="copiedId === target.id" :size="15" aria-hidden="true" /><Copy v-else :size="15" aria-hidden="true" /></button></div></td>
            <td>{{ target.protocol }}</td>
            <td><StatusTag :label="targetStatus[target.status].label" :tone="targetStatus[target.status].tone" /></td>
            <td class="muted-cell">{{ formatDate(target.last_checked_at, true) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </DataState>

  <section class="recovery-note"><h2>攻击边界</h2><p>仅可攻击其他队伍已开放的比赛端口。禁止访问宿主机管理接口、云元数据地址、其他队伍管理网；发现平台侧异常请先联系管理员，不要自行扫描平台网络。</p></section>
</template>
