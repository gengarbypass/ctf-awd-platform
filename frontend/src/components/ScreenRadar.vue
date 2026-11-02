<script setup lang="ts">
import { computed } from 'vue'
import type { ScoreboardRow } from '@/api/types'

const props = defineProps<{ rows: ScoreboardRow[]; maxScore: number }>()

const nodes = computed(() => {
  const count = Math.min(8, props.rows.length)
  return props.rows.slice(0, count).map((row, index) => {
    const angle = -Math.PI / 2 + (index / Math.max(1, count)) * Math.PI * 2
    const ratio = Math.max(0.22, Math.min(1, row.current_score / Math.max(1, props.maxScore)))
    const radius = 34 + ratio * 100
    const x = 160 + Math.cos(angle) * radius
    const y = 160 + Math.sin(angle) * radius
    return {
      row,
      x,
      y,
      labelY: y < 160 ? y - 9 : y + 14,
      top: row.rank === 1,
    }
  })
})
</script>

<template>
  <div class="radar-wrap" role="img" aria-label="前八名战队态势雷达图">
    <svg class="radar-svg" viewBox="0 0 320 320" aria-hidden="true">
      <defs>
        <radialGradient id="radar-core" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#1f63d6" stop-opacity="0.1" />
          <stop offset="100%" stop-color="#eef5ff" stop-opacity="0" />
        </radialGradient>
        <linearGradient id="radar-sweep-fill" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#1f63d6" stop-opacity="0.14" />
          <stop offset="100%" stop-color="#1f63d6" stop-opacity="0" />
        </linearGradient>
      </defs>

      <circle cx="160" cy="160" r="124" fill="url(#radar-core)" />
      <circle v-for="ring in [34, 62, 90, 118, 124]" :key="ring" cx="160" cy="160" :r="ring" class="radar-ring" />
      <line x1="160" y1="36" x2="160" y2="284" class="radar-axis" />
      <line x1="36" y1="160" x2="284" y2="160" class="radar-axis" />
      <line x1="72" y1="72" x2="248" y2="248" class="radar-axis radar-axis--faint" />
      <line x1="248" y1="72" x2="72" y2="248" class="radar-axis radar-axis--faint" />

      <g class="radar-sweep">
        <path d="M160 160 L160 36 A124 124 0 0 1 267 98 Z" fill="url(#radar-sweep-fill)" />
        <line x1="160" y1="160" x2="160" y2="36" class="radar-sweep-line" />
      </g>

      <line
        v-for="node in nodes"
        :key="`line-${node.row.id}`"
        x1="160"
        y1="160"
        :x2="node.x"
        :y2="node.y"
        class="radar-link"
      />

      <g v-for="node in nodes" :key="node.row.id" class="radar-node" :class="{ 'radar-node--top': node.top }">
        <title>{{ node.row.name }} · {{ node.row.current_score }} 分 · 第 {{ node.row.rank }} 名</title>
        <circle :cx="node.x" :cy="node.y" r="10" class="radar-node-halo" />
        <circle :cx="node.x" :cy="node.y" :r="node.top ? 5.5 : 4" class="radar-node-dot" />
        <text :x="node.x" :y="node.labelY" text-anchor="middle" class="radar-label">{{ String(node.row.team_no).padStart(2, '0') }}</text>
      </g>
      <circle cx="160" cy="160" r="3" class="radar-core-dot" />
    </svg>
  </div>
</template>

<style scoped>
.radar-wrap { display: flex; flex: 1; align-items: center; justify-content: center; min-height: 0; padding: 2px 0 0; }
.radar-svg { display: block; width: 100%; height: 100%; max-height: 100%; overflow: visible; }
.radar-ring { fill: none; stroke: rgba(31, 99, 214, 0.15); stroke-width: 0.8; }
.radar-axis { stroke: rgba(31, 99, 214, 0.12); stroke-width: 0.7; }
.radar-axis--faint { stroke-dasharray: 2 5; opacity: 0.6; }
.radar-sweep { transform-origin: 160px 160px; animation: radar-sweep 7s linear infinite; }
.radar-sweep-line { stroke: rgba(31, 99, 214, 0.55); stroke-width: 1; filter: drop-shadow(0 0 4px rgba(31, 99, 214, 0.28)); }
.radar-link { stroke: rgba(31, 99, 214, 0.2); stroke-width: 0.8; stroke-dasharray: 2 4; }
.radar-node-halo { fill: rgba(31, 99, 214, 0.07); stroke: rgba(31, 99, 214, 0.16); stroke-width: 0.7; }
.radar-node-dot { fill: #1f63d6; filter: drop-shadow(0 0 5px rgba(31, 99, 214, 0.5)); }
.radar-node--top .radar-node-dot { fill: #0b2a5b; filter: drop-shadow(0 0 7px rgba(11, 42, 91, 0.55)); }
.radar-node--top .radar-node-halo { fill: rgba(11, 42, 91, 0.08); stroke: rgba(11, 42, 91, 0.35); }
.radar-label { fill: #315b8f; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 10px; letter-spacing: 0.06em; }
.radar-node--top .radar-label { fill: #0b2a5b; }
.radar-core-dot { fill: #1f63d6; filter: drop-shadow(0 0 7px rgba(31, 99, 214, 0.5)); }
@keyframes radar-sweep { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .radar-sweep { animation: none; } }
</style>
