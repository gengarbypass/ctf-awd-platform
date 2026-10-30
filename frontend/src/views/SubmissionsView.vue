<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { RefreshCw } from '@lucide/vue'
import { api } from '@/api/client'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatDate, signed, submissionResult } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'
import FlagSubmitForm from '@/components/FlagSubmitForm.vue'

const route = useRoute()
const router = useRouter()
const { data, loading, loaded, error, load } = useAsyncData(api.submissionsMine, [])
const filter = computed(() => String(route.query.result || 'ALL'))
const rows = computed(() => data.value.filter(item => filter.value === 'ALL' || item.result === filter.value))
const accepted = computed(() => data.value.filter(item => item.result === 'ACCEPTED'))
function setFilter(value: string) { router.replace({ query: value === 'ALL' ? {} : { result: value } }) }
onMounted(load)
</script>

<template>
  <PageHeader title="提交记录" description="仅显示本队验判结果和分数变化，Flag 明文不会写入平台日志。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新记录</button></template>
  </PageHeader>
  <section class="submission-compose"><FlagSubmitForm @accepted="load" /></section>
  <dl class="stat-row stat-row--three"><div><dt>提交总数</dt><dd>{{ data.length }}</dd></div><div><dt>有效攻击</dt><dd>{{ accepted.length }}</dd></div><div><dt>累计攻击得分</dt><dd>+{{ accepted.length * 100 }}</dd></div></dl>
  <div class="table-toolbar"><label for="result-filter">验判结果</label><select id="result-filter" class="input select-input" :value="filter" @change="setFilter(($event.target as HTMLSelectElement).value)"><option value="ALL">全部结果</option><option v-for="(meta, key) in submissionResult" :key="key" :value="key">{{ meta.label }}</option></select></div>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!rows.length" :empty-text="filter === 'ALL' ? '本队尚未提交 Flag。' : '当前筛选条件下没有提交记录。'" @retry="load">
    <div class="table-scroll" tabindex="0" role="region" aria-label="本队提交记录，窄屏可横向滚动"><table v-responsive-table class="data-table"><thead><tr><th>提交时间</th><th>验判结果</th><th>目标队伍</th><th>服务</th><th class="num">本队变化</th><th class="num">对方变化</th><th>请求 ID</th></tr></thead><tbody><tr v-for="item in rows" :key="item.id"><td>{{ formatDate(item.submitted_at, true) }}</td><td><StatusTag :label="submissionResult[item.result].label" :tone="submissionResult[item.result].tone" /></td><td>{{ item.victim_team_name || '未识别' }}</td><td>{{ item.service_name || '未关联' }}</td><td class="num" :class="item.attacker_delta > 0 ? 'text-success' : ''">{{ signed(item.attacker_delta) }}</td><td class="num" :class="item.victim_delta < 0 ? 'text-danger' : ''">{{ signed(item.victim_delta) }}</td><td><code class="request-id" :title="item.request_id">{{ item.request_id.slice(0, 12) }}</code></td></tr></tbody></table></div>
  </DataState>
</template>
