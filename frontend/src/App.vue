<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'

const route = useRoute()
const isLogin = computed(() => route.path === '/login')
</script>

<template>
  <main v-if="isLogin" class="login-shell"><RouterView /></main>
  <AppShell v-else><RouterView /></AppShell>
</template>
