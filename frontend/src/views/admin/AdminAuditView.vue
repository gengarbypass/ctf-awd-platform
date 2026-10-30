<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RefreshCw, Search } from '@lucide/vue'
import { api } from '@/api/client'
import { useAsyncData } from '@/composables/useAsyncData'
import { formatDate } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'

const { data, loading, loaded, error, load } = useAsyncData(api.adminAudit, [])
const query = ref('')
const objectType = ref('ALL')
const types = computed(() => [...new Set(data.value.map(item => item.object_type))])
const rows = computed(() => data.value.filter(item => (objectType.value === 'ALL' || item.object_type === objectType.value) && (!query.value.trim() || `${item.actor_name} ${item.action} ${item.detail} ${item.request_id || ''}`.toLowerCase().includes(query.value.trim().toLowerCase()))))
onMounted(load)
</script>

<template>
  <PageHeader title="审计日志" description="记录认证、队伍、比赛、靶机、公告和人工改分等关键操作，Flag 明文不入日志。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新日志</button></template>
  </PageHeader>
  <div class="audit-filter"><div class="search-field"><Search :size="16" aria-hidden="true" /><input v-model="query" class="input" type="search" aria-label="搜索审计日志" placeholder="操作人、动作、详情或请求 ID" /></div><select v-model="objectType" class="input select-input" aria-label="按对象类型筛选"><option value="ALL">全部对象</option><option v-for="type in types" :key="type" :value="type">{{ type }}</option></select><span>{{ rows.length }} 条记录</span></div>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!rows.length" empty-text="当前筛选条件下没有审计记录。" @retry="load"><div class="table-scroll" tabindex="0" role="region" aria-label="审计日志，窄屏可横向滚动"><table v-responsive-table class="data-table audit-table"><thead><tr><th>时间</th><th>操作人</th><th>动作</th><th>对象</th><th>详情</th><th>请求 ID</th></tr></thead><tbody><tr v-for="item in rows" :key="item.id"><td class="nowrap">{{ formatDate(item.created_at, true) }}</td><td><strong>{{ item.actor_name }}</strong></td><td><code>{{ item.action }}</code></td><td>{{ item.object_type }}<small class="cell-subtitle">{{ item.object_id }}</small></td><td class="audit-detail">{{ item.detail }}</td><td><code>{{ item.request_id?.slice(0, 14) || '系统任务' }}</code></td></tr></tbody></table></div></DataState>
  <p class="audit-note">应用日志采用 JSON 格式并集中投递；时间统一保存为 UTC，页面按本地时区显示。</p>
</template>
