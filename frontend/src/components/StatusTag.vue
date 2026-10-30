<script setup lang="ts">
defineProps<{ label: string; tone?: string }>()
</script>

<template>
  <span class="status-tag" :class="`status-tag--${tone || 'neutral'}`">{{ label }}</span>
</template>
