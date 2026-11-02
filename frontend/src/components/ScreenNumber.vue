<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps<{ value: number; duration?: number }>()

const display = ref(props.value)
let frame = 0
let from = props.value
let startedAt = 0

const formatted = computed(() => display.value.toLocaleString('en-US'))

function animate(to: number) {
  cancelAnimationFrame(frame)
  from = display.value
  startedAt = performance.now()
  const duration = props.duration ?? 700
  const tick = (now: number) => {
    const progress = Math.min(1, (now - startedAt) / duration)
    const eased = 1 - Math.pow(1 - progress, 3)
    display.value = Math.round(from + (to - from) * eased)
    if (progress < 1) frame = requestAnimationFrame(tick)
  }
  frame = requestAnimationFrame(tick)
}

watch(() => props.value, value => {
  if (value !== display.value) animate(value)
})

onBeforeUnmount(() => cancelAnimationFrame(frame))
</script>

<template>
  <span class="screen-number">{{ formatted }}</span>
</template>

<style scoped>
.screen-number {
  display: inline-block;
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum' 1;
  letter-spacing: 0.02em;
}
</style>
