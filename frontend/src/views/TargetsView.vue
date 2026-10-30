<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { RefreshCw } from '@lucide/vue'
import { api } from '@/api/client'
import type { Target } from '@/api/types'
import { useAsyncData } from '@/composables/useAsyncData'
import { useMatchStore } from '@/stores/match'
import { formatDuration } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import TargetTable from '@/components/TargetTable.vue'
import TerminalDialog from '@/components/TerminalDialog.vue'

const matchStore = useMatchStore()
const { data, loading, loaded, error, load } = useAsyncData(api.targetsMine, [])
const actionError = ref('')
const terminalTarget = ref<Target | null>(null)
const healthyCount = computed(() => data.value.filter(item => item.status === 'RUNNING').length)
const abnormalCount = computed(() => data.value.length - healthyCount.value)
async function restart(target: Target) {
  actionError.value = ''
  try {
    await ElMessageBox.confirm(`将重启 ${target.service_name}，保留原数据卷和选手补丁。确认继续？`, '确认重启靶机', { confirmButtonText: '确认重启', cancelButtonText: '取消', type: 'warning' })
    await api.restartTarget(target.id)
    await load()
  } catch (cause) { if (cause !== 'cancel' && cause !== 'close') actionError.value = cause instanceof Error ? cause.message : '重启失败，请重试。' }
}
onMounted(load)
</script>

<template>
  <PageHeader title="我的靶机" description="选手只能访问本队管理网关；重启不会重置镜像或清空数据卷。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新状态</button></template>
  </PageHeader>
  <dl class="stat-row"><div><dt>服务总数</dt><dd>{{ data.length }}</dd></div><div><dt>运行正常</dt><dd>{{ healthyCount }}</dd></div><div><dt>异常或恢复中</dt><dd>{{ abnormalCount }}</dd></div><div><dt>下一轮 Flag</dt><dd>{{ formatDuration(matchStore.roundRemainingSeconds) }}</dd></div></dl>
  <p v-if="actionError" class="inline-error" role="alert">{{ actionError }}</p>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!data.length" empty-text="本队靶机尚未初始化，请联系比赛管理员。" @retry="load"><TargetTable :targets="data" @restart="restart" @terminal="terminalTarget = $event" /></DataState>
  <section class="recovery-note"><h2>异常恢复规则</h2><p>连续两次健康检查失败后触发受控重启。5 分钟内最多自动重启两次，仍异常则转人工处理，服务状态本身不参与加减分。</p></section>
  <TerminalDialog :target="terminalTarget" :open="!!terminalTarget" @close="terminalTarget = null" />
</template>
