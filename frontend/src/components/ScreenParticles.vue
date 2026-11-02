<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  alpha: number
  phase: number
  hue: 'blue' | 'azure' | 'navy'
}

const canvas = ref<HTMLCanvasElement | null>(null)
let context: CanvasRenderingContext2D | null = null
let frame = 0
let width = 0
let height = 0
let dpr = 1
let reducedMotion = false
let particles: Particle[] = []

function randomParticle(): Particle {
  const hueRoll = Math.random()
  return {
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.16,
    vy: (Math.random() - 0.5) * 0.16,
    radius: 0.6 + Math.random() * 1.8,
    alpha: 0.25 + Math.random() * 0.65,
    phase: Math.random() * Math.PI * 2,
    hue: hueRoll > 0.72 ? 'navy' : hueRoll > 0.58 ? 'azure' : 'blue',
  }
}

function resize() {
  const element = canvas.value
  if (!element) return
  width = window.innerWidth
  height = window.innerHeight
  dpr = Math.min(2, window.devicePixelRatio || 1)
  element.width = Math.floor(width * dpr)
  element.height = Math.floor(height * dpr)
  element.style.width = `${width}px`
  element.style.height = `${height}px`
  context = element.getContext('2d')
  if (!context) return
  context.setTransform(dpr, 0, 0, dpr, 0, 0)
  const count = Math.max(36, Math.min(82, Math.floor((width * height) / 24000)))
  particles = Array.from({ length: count }, randomParticle)
  drawFrame(performance.now())
}

function drawFrame(time: number) {
  if (!context) return
  context.clearRect(0, 0, width, height)
  context.globalCompositeOperation = 'source-over'

  for (const particle of particles) {
    if (!reducedMotion) {
      particle.x += particle.vx
      particle.y += particle.vy
      if (particle.x < -20) particle.x = width + 20
      if (particle.x > width + 20) particle.x = -20
      if (particle.y < -20) particle.y = height + 20
      if (particle.y > height + 20) particle.y = -20
    }
    const flicker = 0.72 + Math.sin(time * 0.0012 + particle.phase) * 0.28
    const color = particle.hue === 'navy'
      ? `rgba(11, 42, 91, ${particle.alpha * flicker * 0.72})`
      : particle.hue === 'azure'
        ? `rgba(47, 128, 237, ${particle.alpha * flicker * 0.62})`
        : `rgba(31, 99, 214, ${particle.alpha * flicker * 0.58})`
    context.beginPath()
    context.fillStyle = color
    context.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2)
    context.fill()
  }

  for (let index = 0; index < particles.length; index += 1) {
    const first = particles[index]
    for (let other = index + 1; other < particles.length; other += 1) {
      const second = particles[other]
      const dx = first.x - second.x
      const dy = first.y - second.y
      const distance = Math.sqrt(dx * dx + dy * dy)
      if (distance > 150) continue
      context.beginPath()
      context.strokeStyle = `rgba(31, 99, 214, ${(1 - distance / 150) * 0.12})`
      context.lineWidth = 0.7
      context.moveTo(first.x, first.y)
      context.lineTo(second.x, second.y)
      context.stroke()
    }
  }
  context.globalCompositeOperation = 'source-over'
}

function loop(time: number) {
  drawFrame(time)
  frame = requestAnimationFrame(loop)
}

onMounted(() => {
  reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  resize()
  if (!reducedMotion) frame = requestAnimationFrame(loop)
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  window.removeEventListener('resize', resize)
})
</script>

<template>
  <canvas ref="canvas" class="screen-particles" aria-hidden="true" />
</template>

<style scoped>
.screen-particles {
  position: absolute;
  inset: 0;
  z-index: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
</style>
