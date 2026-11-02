<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'

const route = useRoute()
const isLogin = computed(() => route.path === '/login')
const isBare = computed(() => route.meta.bare === true)
</script>

<template>
  <main v-if="isLogin" class="login-shell"><RouterView /></main>
  <RouterView v-else-if="isBare" />
  <AppShell v-else><RouterView /></AppShell>
</template>
