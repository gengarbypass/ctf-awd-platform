<script setup lang="ts">
import { onMounted } from 'vue'
import { Bell, Pin, RefreshCw } from '@lucide/vue'
import { api } from '@/api/client'
import { useAsyncData } from '@/composables/useAsyncData'
import { announcementLevel, formatFullDate } from '@/utils/format'
import PageHeader from '@/components/PageHeader.vue'
import DataState from '@/components/DataState.vue'
import StatusTag from '@/components/StatusTag.vue'

const { data, loading, loaded, error, load } = useAsyncData(api.announcements, [])
onMounted(load)
</script>

<template>
  <PageHeader title="公告" description="比赛时间、轮换异常和平台服务变更以公告为准。">
    <template #actions><button class="button button--secondary" type="button" :disabled="loading" @click="load"><RefreshCw :size="16" aria-hidden="true" />刷新公告</button></template>
  </PageHeader>
  <DataState :loading="loading" :loaded="loaded" :error="error" :empty="!data.length" empty-text="管理员尚未发布公告。" @retry="load">
    <div class="announcement-feed"><article v-for="notice in data" :key="notice.id" class="announcement-item" :class="{ 'is-pinned': notice.pinned }"><div class="announcement-item__icon"><Pin v-if="notice.pinned" :size="19" aria-label="置顶公告" /><Bell v-else :size="19" aria-hidden="true" /></div><div class="announcement-item__body"><h2>{{ notice.title }}</h2><div class="announcement-item__meta"><StatusTag :label="announcementLevel[notice.level].label" :tone="announcementLevel[notice.level].tone" /><time :datetime="notice.published_at">{{ formatFullDate(notice.published_at) }}</time><span v-if="notice.pinned">已置顶</span></div><p>{{ notice.content }}</p></div></article></div>
  </DataState>
</template>
