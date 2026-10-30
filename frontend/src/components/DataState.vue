<script setup lang="ts">
import { AlertCircle, Inbox, RotateCw } from '@lucide/vue'

defineProps<{ loading: boolean; loaded: boolean; error: string; empty: boolean; emptyText?: string }>()
const emit = defineEmits<{ retry: [] }>()
</script>

<template>
  <div v-if="loading && !loaded" class="data-state" aria-live="polite">
    <div class="skeleton-stack" aria-hidden="true"><span /><span /><span /><span /></div>
    <p>正在读取平台数据…</p>
  </div>
  <div v-else-if="error && !loaded" class="data-state" role="alert">
    <AlertCircle :size="24" aria-hidden="true" />
    <p>{{ error }}</p>
    <button class="button button--secondary" type="button" @click="emit('retry')"><RotateCw :size="16" aria-hidden="true" />重新加载</button>
  </div>
  <div v-else-if="empty" class="data-state">
    <Inbox :size="24" aria-hidden="true" />
    <p>{{ emptyText || '当前没有可显示的记录。' }}</p>
    <slot name="empty-action" />
  </div>
  <template v-else><p v-if="error" class="inline-error" role="alert">{{ error }}</p><slot /></template>
</template>
