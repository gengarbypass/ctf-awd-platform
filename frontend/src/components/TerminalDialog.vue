<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { SquareTerminal } from '@lucide/vue'
import { isDemo } from '@/api/client'
import type { Target } from '@/api/types'

const props = defineProps<{ target: Target | null; open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const terminalElement = ref<HTMLElement | null>(null)
const connectionState = ref('尚未连接')
let terminal: import('@xterm/xterm').Terminal | undefined
let fitAddon: import('@xterm/addon-fit').FitAddon | undefined
let socket: WebSocket | undefined
let observer: ResizeObserver | undefined

async function connect() {
  if (!props.target || isDemo || !terminalElement.value) return
  connectionState.value = '正在建立加密连接…'
  const [{ Terminal }, { FitAddon }] = await Promise.all([import('@xterm/xterm'), import('@xterm/addon-fit')])
  terminal = new Terminal({ cursorBlink: true, fontSize: 14, scrollback: 3000 })
  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalElement.value)
  await nextTick()
  fitAddon.fit()
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const base = import.meta.env.VITE_API_BASE || '/api/v1'
  socket = new WebSocket(`${protocol}//${location.host}${base}/terminal/${props.target.id}/ws`)
  socket.binaryType = 'arraybuffer'
  socket.onopen = () => {
    connectionState.value = '已连接'
    socket?.send(JSON.stringify({ type: 'resize', cols: terminal?.cols, rows: terminal?.rows }))
  }
  socket.onmessage = event => {
    if (typeof event.data === 'string') terminal?.write(event.data)
    else terminal?.write(new Uint8Array(event.data))
  }
  socket.onerror = () => { connectionState.value = '连接异常，请关闭终端后重试。' }
  socket.onclose = () => { connectionState.value = '连接已关闭' }
  terminal.onData(data => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'input', data })) })
  terminal.onResize(size => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'resize', ...size })) })
  observer = new ResizeObserver(() => fitAddon?.fit())
  observer.observe(terminalElement.value)
}

function disconnect() {
  observer?.disconnect(); observer = undefined
  socket?.close(); socket = undefined
  terminal?.dispose(); terminal = undefined
  fitAddon = undefined
  connectionState.value = '尚未连接'
}

watch(() => props.open, async open => {
  if (open) { await nextTick(); await connect() } else disconnect()
})
onBeforeUnmount(disconnect)
</script>

<template>
  <el-dialog :model-value="open" :title="target ? `${target.service_name} Web 终端` : 'Web 终端'" width="min(920px, 92vw)" class="terminal-dialog" @close="emit('close')">
    <div class="terminal-toolbar"><SquareTerminal :size="17" aria-hidden="true" /><span>{{ target?.container_name }}</span><span>{{ isDemo ? '演示模式未连接靶机' : connectionState }}</span></div>
    <div v-if="isDemo" class="terminal-unavailable"><SquareTerminal :size="28" aria-hidden="true" /><p>当前为前端演示模式，没有连接真实靶机。</p><small>启动 FastAPI 与 SSH 终端代理后，可在此管理本队服务。</small></div>
    <div v-else ref="terminalElement" class="terminal-canvas" :aria-label="`${target?.service_name || ''} 终端`" />
    <p class="terminal-note">终端仅允许访问本队管理网关。操作日志按平台审计策略保存。</p>
  </el-dialog>
</template>
