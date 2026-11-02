<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  Activity, Bell, Crown, LogOut, Maximize2, Minimize2, Radio, Swords, Trophy,
  Users, Wifi, WifiOff,
} from '@lucide/vue'
import { api, createEventSource, isDemo } from '@/api/client'
import type { Announcement, Match, Scoreboard, ScoreboardRow, TargetStatus } from '@/api/types'
import { announcementLevel, formatDuration, matchStatus, signed, targetStatus } from '@/utils/format'
import ScreenNumber from '@/components/ScreenNumber.vue'
import ScreenParticles from '@/components/ScreenParticles.vue'
import ScreenRadar from '@/components/ScreenRadar.vue'

type FeedTone = 'up' | 'down' | 'info' | 'warn'

interface FeedItem {
  id: string
  kind: 'score' | 'notice' | 'match' | 'system'
  title: string
  detail: string
  at: number
  tone: FeedTone
}

const scoreboard = ref<Scoreboard | null>(null)
const screenTitle = '网安师市行实战对抗'
const match = ref<Match | null>(null)
const notices = ref<Announcement[]>([])
const loading = ref(true)
const error = ref('')
const connected = ref(false)
const isFullscreen = ref(false)
const now = ref(Date.now())
const serverOffset = ref(0)
const lastSync = ref(0)
const feed = ref<FeedItem[]>([])
const scoreFlash = reactive<Record<string, { delta: number; tone: 'up' | 'down' }>>({})
const rankFlash = reactive<Record<string, 'up' | 'down'>>({})

const flashTimers = new Map<string, number>()
const rankTimers = new Map<string, number>()
let previousScores = new Map<string, number>()
let previousRanks = new Map<string, number>()
let previousNotices = new Set<string>()
let previousStatus: string | null = null
let initialized = false
let feedSequence = 0
let loadSequence = 0
let clockTimer: number | undefined
let refreshTimer: number | undefined
let debounceTimer: number | undefined
let disconnect: (() => void) | undefined
let fullscreenRequested = false

const rows = computed(() => scoreboard.value?.rows ?? [])
const currentStatus = computed(() => match.value ? matchStatus[match.value.status] : { label: '等待比赛', tone: 'neutral' })
const maxScore = computed(() => Math.max(1, ...rows.value.map(row => row.current_score)))
const remainingSeconds = computed(() => {
  const current = match.value
  if (!current || !['RUNNING', 'PAUSED'].includes(current.status)) return 0
  const reference = current.status === 'PAUSED' && current.paused_at
    ? new Date(current.paused_at).getTime()
    : now.value + serverOffset.value
  return Math.max(0, Math.floor((new Date(current.ends_at).getTime() - reference) / 1000))
})
const remainingLabel = computed(() => match.value ? formatDuration(remainingSeconds.value) : '--:--:--')
const stats = computed(() => {
  const teamRows = rows.value
  const services = teamRows.flatMap(row => row.services)
  const running = services.filter(service => service.status === 'RUNNING').length
  return {
    teams: teamRows.length,
    attacks: teamRows.reduce((total, row) => total + row.attack_count, 0),
    breaches: teamRows.reduce((total, row) => total + row.breached_count, 0),
    healthy: running,
    services: services.length,
    healthPct: services.length ? Math.round((running / services.length) * 100) : 0,
  }
})
const topNotice = computed<Announcement | null>(() => notices.value.find(item => item.pinned) ?? notices.value[0] ?? null)
const noticePreview = computed(() => notices.value.filter(item => item.id !== topNotice.value?.id).slice(0, 2))
const tickerText = computed(() => notices.value.length
  ? notices.value.map(item => `${item.title} // ${item.content}`).join('　　 ● 　　')
  : '暂无公告')
const tickerCopies = computed(() => [tickerText.value, tickerText.value])
const lastSyncLabel = computed(() => formatClock(lastSync.value))

function formatClock(value: number) {
  if (!Number.isFinite(value) || value <= 0) return '--:--:--'
  return new Date(value).toLocaleTimeString('zh-CN', { hour12: false })
}

function barWidth(row: ScoreboardRow) {
  return Math.max(4, Math.round((Math.max(0, row.current_score) / maxScore.value) * 100))
}

function serviceTone(status: TargetStatus) {
  return targetStatus[status]?.tone ?? 'neutral'
}

function serviceLabel(row: ScoreboardRow, service: ScoreboardRow['services'][number]) {
  return `${row.name} / ${service.service_name}：${targetStatus[service.status]?.label ?? service.status}`
}

function rankNumber(rank: number) {
  return String(rank).padStart(2, '0')
}

function pushFeed(item: Omit<FeedItem, 'id' | 'at'>) {
  feedSequence += 1
  feed.value = [{ ...item, id: `feed-${feedSequence}`, at: Date.now() }, ...feed.value].slice(0, 8)
}

function flashScore(teamId: string, delta: number) {
  scoreFlash[teamId] = { delta, tone: delta > 0 ? 'up' : 'down' }
  const oldTimer = flashTimers.get(teamId)
  if (oldTimer) window.clearTimeout(oldTimer)
  flashTimers.set(teamId, window.setTimeout(() => {
    delete scoreFlash[teamId]
    flashTimers.delete(teamId)
  }, 3200))
}

function flashRank(teamId: string, direction: 'up' | 'down') {
  rankFlash[teamId] = direction
  const oldTimer = rankTimers.get(teamId)
  if (oldTimer) window.clearTimeout(oldTimer)
  rankTimers.set(teamId, window.setTimeout(() => {
    delete rankFlash[teamId]
    rankTimers.delete(teamId)
  }, 3600))
}

function applySnapshot(board: Scoreboard, current: Match | null, noticeList: Announcement[]) {
  const nextScores = new Map<string, number>()
  const nextRanks = new Map<string, number>()
  const nextNotices = new Set(noticeList.map(item => item.id))
  const nextStatus = current?.status ?? null

  for (const row of board.rows) {
    nextScores.set(row.id, row.current_score)
    nextRanks.set(row.id, row.rank)
  }

  if (initialized) {
    for (const row of board.rows) {
      const beforeScore = previousScores.get(row.id)
      if (beforeScore !== undefined && beforeScore !== row.current_score) {
        const delta = row.current_score - beforeScore
        flashScore(row.id, delta)
        pushFeed({
          kind: 'score',
          title: delta > 0 ? `${row.name} 得分` : `${row.name} 被攻破`,
          detail: `${delta > 0 ? '+' : ''}${delta} 分 · 当前 ${row.current_score}`,
          tone: delta > 0 ? 'up' : 'down',
        })
      }
      const beforeRank = previousRanks.get(row.id)
      if (beforeRank !== undefined && beforeRank !== row.rank) {
        flashRank(row.id, row.rank < beforeRank ? 'up' : 'down')
      }
    }
    if (nextStatus && previousStatus && nextStatus !== previousStatus) {
      pushFeed({
        kind: 'match',
        title: `比赛状态：${matchStatus[nextStatus].label}`,
        detail: current ? `第 ${current.current_round} 轮 · ${current.round_seconds} 秒轮换` : '比赛状态已更新',
        tone: nextStatus === 'FINISHED' ? 'warn' : 'info',
      })
    }
    for (const notice of noticeList) {
      if (!previousNotices.has(notice.id)) {
        pushFeed({ kind: 'notice', title: '新公告', detail: notice.title, tone: notice.level === 'CRITICAL' ? 'warn' : 'info' })
      }
    }
  } else {
    initialized = true
    if (board.rows.length) {
      pushFeed({ kind: 'system', title: '实时计分已接入', detail: `${board.rows.length} 支队伍 · 等待下一次有效攻击`, tone: 'info' })
    }
  }

  scoreboard.value = board
  match.value = current
  notices.value = noticeList
  previousScores = nextScores
  previousRanks = nextRanks
  previousNotices = nextNotices
  previousStatus = nextStatus
  lastSync.value = Date.now()
}

async function load() {
  const sequence = ++loadSequence
  try {
    const [board, current, noticeList] = await Promise.all([api.scoreboard(), api.match(), api.announcements()])
    if (sequence !== loadSequence) return
    const currentMatch = current as Match | null
    if (currentMatch) serverOffset.value = new Date(currentMatch.server_time).getTime() - Date.now()
    applySnapshot(board, currentMatch, noticeList)
    error.value = ''
  } catch (cause) {
    if (sequence !== loadSequence) return
    error.value = cause instanceof Error ? cause.message : '比赛数据加载失败，请检查网络。'
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function toggleFullscreen() {
  try {
    if (!document.fullscreenElement) {
      await document.documentElement.requestFullscreen()
      fullscreenRequested = true
    } else {
      await document.exitFullscreen()
      fullscreenRequested = false
    }
  } catch {
    // 浏览器拒绝全屏时保持当前页面，不打断大屏展示。
  }
}

function onFullscreenChange() {
  isFullscreen.value = Boolean(document.fullscreenElement)
  if (!isFullscreen.value) fullscreenRequested = false
}

function onKeydown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
  if (event.key === 'f' || event.key === 'F') {
    event.preventDefault()
    void toggleFullscreen()
  }
}

function onVisibilityChange() {
  if (document.visibilityState === 'visible') void load()
}

function scheduleRefresh() {
  if (debounceTimer) return
  debounceTimer = window.setTimeout(() => {
    debounceTimer = undefined
    void load()
  }, 260)
}

function tick() {
  now.value = Date.now()
}

onMounted(async () => {
  await load()
  disconnect = createEventSource(scheduleRefresh, state => { connected.value = state })
  clockTimer = window.setInterval(tick, 1000)
  refreshTimer = window.setInterval(() => { void load() }, 30000)
  document.addEventListener('fullscreenchange', onFullscreenChange)
  document.addEventListener('visibilitychange', onVisibilityChange)
  window.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  disconnect?.()
  if (clockTimer) window.clearInterval(clockTimer)
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (debounceTimer) window.clearTimeout(debounceTimer)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  window.removeEventListener('keydown', onKeydown)
  flashTimers.forEach(timer => window.clearTimeout(timer))
  rankTimers.forEach(timer => window.clearTimeout(timer))
  if (fullscreenRequested && document.fullscreenElement) {
    void document.exitFullscreen().catch(() => undefined)
  }
})
</script>

<template>
  <main class="bigscreen">
    <ScreenParticles />
    <div class="ambient ambient--cyan" />
    <div class="ambient ambient--violet" />
    <div class="grid-overlay" />
    <div class="scanline" />

    <header class="bs-header">
      <div class="brand-block">
        <img class="brand-mark brand-mark--logo" src="/taru-cyber-logo.png" alt="塔里木大学网络安全学院" />
        <div class="brand-copy"><strong>塔大网安 · 师市行</strong><span>AWD LIVE SCOREBOARD</span></div>
      </div>

      <div class="match-block">
        <div class="match-topline">
          <span class="status-pill" :class="`tone-${currentStatus.tone}`"><i class="status-pulse" />{{ currentStatus.label }}</span>
          <span class="match-code">TARC // AWD // {{ match ? 'ONLINE' : 'STANDBY' }}</span>
          <span v-if="isDemo" class="demo-chip">DEMO</span>
        </div>
        <h1>{{ screenTitle }}</h1>
        <div class="match-meta">
          <span>ROUND <b>{{ String(match?.current_round ?? 0).padStart(2, '0') }}</b></span>
          <span>{{ match?.round_seconds ?? 300 }}S ROTATION</span>
          <span v-if="match?.score_frozen" class="frozen-label">SCOREBOARD FROZEN</span>
        </div>
      </div>

      <div class="header-actions">
        <div class="live-chip" :class="{ 'is-offline': !connected }">
          <Wifi v-if="connected" :size="15" aria-hidden="true" />
          <WifiOff v-else :size="15" aria-hidden="true" />
          <span>{{ connected ? 'LIVE' : 'RECONNECT' }}</span>
        </div>
        <div class="clock-block">
          <span>REMAINING</span>
          <strong>{{ remainingLabel }}</strong>
        </div>
        <button class="icon-action" type="button" :title="isFullscreen ? '退出全屏' : '全屏'" @click="toggleFullscreen">
          <Minimize2 v-if="isFullscreen" :size="18" aria-hidden="true" />
          <Maximize2 v-else :size="18" aria-hidden="true" />
        </button>
        <RouterLink class="icon-action" to="/scoreboard" title="返回计分板">
          <LogOut :size="18" aria-hidden="true" />
        </RouterLink>
      </div>
    </header>

    <section class="bs-body">
      <section class="panel ranking-panel">
        <div class="panel-head">
          <div class="panel-title">
            <span class="eyebrow"><Trophy :size="14" aria-hidden="true" /> LIVE RANKING</span>
            <h2>实时战队排行</h2>
          </div>
          <div class="panel-side">
            <span class="rank-count">{{ stats.teams }} TEAMS</span>
            <span>SYNC {{ lastSyncLabel }}</span>
          </div>
        </div>

        <div class="ranking-head">
          <span>RANK</span><span>TEAM</span><span>ATK / DEF</span><span>SERVICES</span><span>SCORE</span>
        </div>

        <TransitionGroup name="rank" tag="ol" class="ranking-list">
          <li
            v-for="row in rows"
            :key="row.id"
            class="rank-row"
            :class="[
              row.rank <= 3 ? `rank-row--${row.rank}` : 'rank-row--rest',
              { 'is-gain': scoreFlash[row.id]?.tone === 'up', 'is-loss': scoreFlash[row.id]?.tone === 'down' },
            ]"
          >
            <div class="rank-cell">
              <span class="rank-number">{{ rankNumber(row.rank) }}</span>
              <Crown v-if="row.rank === 1" class="crown" :size="19" aria-label="第一名" />
              <span v-if="rankFlash[row.id]" class="rank-arrow" :class="`rank-arrow--${rankFlash[row.id]}`">{{ rankFlash[row.id] === 'up' ? '▲' : '▼' }}</span>
            </div>
            <div class="team-cell">
              <div class="team-name"><strong>{{ row.name }}</strong><span>#{{ String(row.team_no).padStart(2, '0') }}</span></div>
              <div class="team-sub">{{ row.member_count }} MEMBERS</div>
              <div class="score-track"><i :style="{ width: `${barWidth(row)}%` }" /></div>
            </div>
            <div class="combat-cell">
              <span class="stat-up"><Swords :size="13" aria-hidden="true" />{{ row.attack_count }}</span>
              <span class="stat-down">{{ row.breached_count }}</span>
            </div>
            <div class="service-cell">
              <span
                v-for="service in row.services"
                :key="service.service_code"
                class="service-dot"
                :class="`tone-${serviceTone(service.status)}`"
                :title="serviceLabel(row, service)"
              />
            </div>
            <div class="score-cell">
              <ScreenNumber :value="row.current_score" />
              <span v-if="scoreFlash[row.id]" class="score-delta" :class="`score-delta--${scoreFlash[row.id].tone}`">
                {{ signed(scoreFlash[row.id].delta) }}
              </span>
            </div>
          </li>
        </TransitionGroup>

        <div v-if="!rows.length" class="ranking-empty">
          <Trophy :size="22" aria-hidden="true" />
          <span>等待队伍与计分数据接入</span>
        </div>
      </section>

      <aside class="side-panel">
        <div class="stat-grid">
          <article class="stat-card stat-card--teams">
            <Users :size="17" aria-hidden="true" />
            <span>参赛队伍</span>
            <strong>{{ stats.teams }}</strong>
            <small>ACTIVE ROSTER</small>
          </article>
          <article class="stat-card stat-card--attack">
            <Swords :size="17" aria-hidden="true" />
            <span>有效攻击</span>
            <strong>{{ stats.attacks }}</strong>
            <small>TOTAL CAPTURES</small>
          </article>
          <article class="stat-card stat-card--breach">
            <Activity :size="17" aria-hidden="true" />
            <span>服务健康</span>
            <strong>{{ stats.healthPct }}<em>%</em></strong>
            <small>{{ stats.healthy }} / {{ stats.services }} UP</small>
          </article>
          <article class="stat-card stat-card--round">
            <Radio :size="17" aria-hidden="true" />
            <span>轮次</span>
            <strong>{{ String(match?.current_round ?? 0).padStart(2, '0') }}</strong>
            <small>{{ currentStatus.label }}</small>
          </article>
        </div>

        <section class="panel radar-panel">
          <div class="panel-head">
            <div class="panel-title">
              <span class="eyebrow"><Radio :size="13" aria-hidden="true" /> ORBIT</span>
              <h2>战场态势</h2>
            </div>
            <span class="panel-side">TOP 8</span>
          </div>
          <div class="radar-body">
            <ScreenRadar :rows="rows" :max-score="maxScore" />
            <ol class="radar-legend">
              <li v-for="row in rows.slice(0, 4)" :key="row.id" :class="`radar-legend--${row.rank <= 3 ? row.rank : 'rest'}`">
                <span>{{ rankNumber(row.rank) }}</span>
                <strong>{{ row.name }}</strong>
                <em>{{ row.current_score }}</em>
              </li>
            </ol>
          </div>
        </section>

        <section class="panel feed-panel">
          <div class="panel-head">
            <div class="panel-title">
              <span class="eyebrow"><Radio :size="13" aria-hidden="true" /> LIVE FEED</span>
              <h2>实时战报</h2>
            </div>
            <span class="feed-count">{{ feed.length }}</span>
          </div>
          <TransitionGroup name="feed" tag="ul" class="feed-list">
            <li v-for="item in feed" :key="item.id" class="feed-item" :class="`feed-item--${item.tone}`">
              <span class="feed-time">{{ formatClock(item.at) }}</span>
              <div class="feed-copy"><strong>{{ item.title }}</strong><small>{{ item.detail }}</small></div>
              <span class="feed-node" />
            </li>
          </TransitionGroup>
        </section>

        <section class="panel notice-panel">
          <div class="panel-head">
            <div class="panel-title">
              <span class="eyebrow"><Bell :size="13" aria-hidden="true" /> BULLETIN</span>
              <h2>赛事公告</h2>
            </div>
            <span class="notice-count">{{ notices.length }}</span>
          </div>
          <article v-if="topNotice" class="notice-feature" :class="`notice-feature--${topNotice.level.toLowerCase()}`">
            <div class="notice-top">
              <span class="notice-level">{{ announcementLevel[topNotice.level].label }}</span>
              <span v-if="topNotice.pinned" class="pin-mark">PINNED</span>
              <time>{{ formatClock(new Date(topNotice.published_at).getTime()) }}</time>
            </div>
            <h3>{{ topNotice.title }}</h3>
            <p>{{ topNotice.content }}</p>
          </article>
          <ul v-if="noticePreview.length" class="notice-list">
            <li v-for="notice in noticePreview" :key="notice.id">
              <span>{{ announcementLevel[notice.level].label }}</span>
              <strong>{{ notice.title }}</strong>
            </li>
          </ul>
          <p v-if="!topNotice" class="notice-empty">暂无赛事公告</p>
        </section>
      </aside>
    </section>

    <footer class="bs-footer">
      <div class="ticker-label"><Bell :size="15" aria-hidden="true" /><span>公告</span></div>
      <div class="ticker-window">
        <div class="ticker-track"><span v-for="(copy, index) in tickerCopies" :key="index">{{ copy }}</span></div>
      </div>
      <div class="footer-sync">
        <span>{{ stats.teams }} TEAMS</span>
        <span>{{ stats.attacks }} ATK / {{ stats.breaches }} HIT</span>
      </div>
    </footer>

    <div v-if="error && rows.length" class="error-strip" role="alert">{{ error }}</div>

    <div v-if="loading" class="boot-overlay">
      <div class="boot-mark">TARC<span>//</span>AWD</div>
      <div class="boot-ring" aria-hidden="true" />
      <p>正在接入实时计分数据…</p>
    </div>
    <div v-else-if="error && !rows.length" class="boot-overlay boot-overlay--error">
      <div class="boot-mark">TARC<span>//</span>AWD</div>
      <p>{{ error }}</p>
      <button class="boot-retry" type="button" @click="load">重新连接</button>
    </div>
  </main>
</template>

<style scoped>
.bigscreen {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: clamp(10px, 1.4vh, 18px);
  overflow: hidden;
  padding: clamp(14px, 2vh, 26px) clamp(16px, 2.4vw, 40px);
  color: #eaffff;
  background:
    radial-gradient(circle at 14% -12%, rgba(40, 130, 255, 0.24), transparent 36%),
    radial-gradient(circle at 88% 4%, rgba(142, 62, 255, 0.2), transparent 34%),
    radial-gradient(circle at 50% 118%, rgba(0, 255, 200, 0.1), transparent 42%),
    #04070e;
  font-family: var(--font-body, 'Noto Sans SC', 'Microsoft YaHei', sans-serif);
  isolation: isolate;
}

.bigscreen::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 1;
  pointer-events: none;
  background: radial-gradient(ellipse at center, transparent 48%, rgba(0, 0, 0, 0.55) 100%);
}

.ambient {
  position: absolute;
  z-index: 0;
  width: 42vw;
  height: 42vw;
  border-radius: 999px;
  filter: blur(100px);
  opacity: 0.28;
  pointer-events: none;
  animation: ambient-drift 16s ease-in-out infinite alternate;
}
.ambient--cyan { top: -20vw; left: -10vw; background: #0e86ff; }
.ambient--violet { right: -12vw; bottom: -20vw; background: #8d3cff; animation-delay: -7s; }

.grid-overlay {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.68;
  background-image:
    linear-gradient(rgba(76, 210, 255, 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(76, 210, 255, 0.055) 1px, transparent 1px);
  background-size: 64px 64px;
  mask-image: radial-gradient(ellipse at center, #000 22%, transparent 76%);
  animation: grid-drift 28s linear infinite;
}

.scanline {
  position: absolute;
  top: -24%;
  left: 0;
  z-index: 2;
  width: 100%;
  height: 22%;
  pointer-events: none;
  background: linear-gradient(to bottom, transparent, rgba(90, 240, 255, 0.07), transparent);
  animation: scan 8s linear infinite;
}

.bs-header {
  position: relative;
  z-index: 3;
  display: grid;
  grid-template-columns: minmax(200px, 1fr) auto minmax(300px, 1fr);
  align-items: center;
  gap: clamp(12px, 2vw, 30px);
  min-height: 82px;
}

.brand-block { display: flex; align-items: center; gap: 13px; min-width: 0; }
.brand-mark {
  display: grid;
  place-items: center;
  width: 58px;
  height: 58px;
  border: 1px solid rgba(95, 250, 255, 0.62);
  color: #a6fbff;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
  clip-path: polygon(0 0, 84% 0, 100% 16%, 100% 100%, 16% 100%, 0 84%);
  background: linear-gradient(145deg, rgba(34, 213, 255, 0.16), rgba(110, 58, 255, 0.08));
  box-shadow: inset 0 0 24px rgba(53, 228, 255, 0.12), 0 0 28px rgba(53, 228, 255, 0.12);
}
.brand-copy { display: flex; flex-direction: column; min-width: 0; }
.brand-copy strong { font-size: clamp(0.9rem, 1.1vw, 1.12rem); letter-spacing: 0.08em; white-space: nowrap; }
.brand-copy span { margin-top: 3px; color: #6f88a7; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 9px; letter-spacing: 0.18em; }

.match-block { min-width: 0; text-align: center; }
.match-topline { display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; }
.match-code { color: #5f7d9e; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 9px; letter-spacing: 0.16em; }
.demo-chip { padding: 2px 6px; border: 1px solid rgba(255, 190, 70, 0.5); border-radius: 4px; color: #ffcf70; font-family: ui-monospace, monospace; font-size: 9px; letter-spacing: 0.12em; }
.match-block h1 {
  max-width: 42ch;
  margin: 7px auto 5px;
  overflow: hidden;
  color: #f2fdff;
  font-family: var(--font-display, inherit);
  font-size: clamp(1.2rem, 2.2vw, 2.2rem);
  font-weight: 800;
  letter-spacing: 0.1em;
  line-height: 1.15;
  text-overflow: ellipsis;
  text-shadow: 0 0 24px rgba(76, 238, 255, 0.38);
  white-space: nowrap;
}
.match-meta { display: flex; align-items: center; justify-content: center; gap: 16px; color: #7693b5; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 10px; letter-spacing: 0.12em; }
.match-meta b { color: #c5f8ff; font-weight: 600; }
.frozen-label { color: #ffd166; }

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 9px;
  border: 1px solid currentColor;
  border-radius: 999px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 9px;
  letter-spacing: 0.12em;
  line-height: 1.5;
}
.status-pulse { width: 5px; height: 5px; border-radius: 50%; background: currentColor; box-shadow: 0 0 8px currentColor; animation: pulse 1.8s ease-in-out infinite; }
.tone-success { color: #6dffc1; }
.tone-warning { color: #ffd166; }
.tone-danger { color: #ff6b9d; }
.tone-info { color: #62dcff; }
.tone-neutral { color: #91a8c4; }

.header-actions { display: flex; align-items: center; justify-content: flex-end; gap: 11px; }
.live-chip { display: inline-flex; align-items: center; gap: 6px; color: #67ffd0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 9px; letter-spacing: 0.15em; }
.live-chip.is-offline { color: #ff9f70; }
.live-chip svg { filter: drop-shadow(0 0 5px currentColor); }
.clock-block { display: flex; flex-direction: column; align-items: flex-end; gap: 1px; }
.clock-block span { color: #5f7d9e; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 8px; letter-spacing: 0.16em; }
.clock-block strong { color: #f3ffff; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: clamp(1rem, 1.7vw, 1.55rem); font-weight: 500; letter-spacing: 0.05em; text-shadow: 0 0 18px rgba(84, 231, 255, 0.42); }

.icon-action {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid rgba(92, 210, 255, 0.22);
  border-radius: 8px;
  color: #86a6c8;
  background: rgba(10, 24, 44, 0.5);
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
}
.icon-action:hover { color: #d7ffff; border-color: rgba(92, 240, 255, 0.65); background: rgba(22, 64, 98, 0.55); }

.bs-body { position: relative; z-index: 3; display: grid; grid-template-columns: minmax(0, 1.66fr) minmax(310px, 0.84fr); gap: clamp(12px, 1.4vw, 22px); min-height: 0; }

.panel {
  position: relative;
  min-height: 0;
  overflow: hidden;
  border: 1px solid rgba(83, 196, 255, 0.17);
  border-radius: 16px;
  background: linear-gradient(155deg, rgba(9, 22, 42, 0.9), rgba(4, 10, 23, 0.82));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05), 0 20px 70px rgba(0, 0, 0, 0.36);
  backdrop-filter: blur(12px);
}
.panel::before {
  content: '';
  position: absolute;
  top: 0;
  right: 8%;
  left: 8%;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(92, 238, 255, 0.72), transparent);
  opacity: 0.7;
}

.ranking-panel { display: flex; flex-direction: column; padding: clamp(13px, 1.7vh, 22px) clamp(14px, 1.6vw, 24px) 8px; }
.panel-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; }
.panel-title { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.eyebrow { display: inline-flex; align-items: center; gap: 5px; color: #57d8ff; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 9px; letter-spacing: 0.16em; }
.panel-title h2 { margin: 0; color: #e9fbff; font-family: var(--font-display, inherit); font-size: clamp(1rem, 1.5vw, 1.38rem); font-weight: 700; letter-spacing: 0.08em; }
.panel-side { display: flex; align-items: center; gap: 14px; color: #63819f; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 9px; letter-spacing: 0.1em; white-space: nowrap; }
.rank-count { color: #a9f7ff; }

.ranking-head {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) 96px 74px 118px;
  gap: 10px;
  margin-top: 14px;
  padding: 0 8px 7px;
  border-bottom: 1px solid rgba(82, 200, 255, 0.12);
  color: #536f8e;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 8px;
  letter-spacing: 0.16em;
}
.ranking-head span:last-child { text-align: right; }

.ranking-list { display: flex; flex: 1; flex-direction: column; min-height: 0; margin: 0; padding: 0; overflow: auto; list-style: none; scrollbar-width: none; }
.ranking-list::-webkit-scrollbar { display: none; }

.rank-row {
  position: relative;
  display: grid;
  flex: 1 1 auto;
  grid-template-columns: 58px minmax(0, 1fr) 96px 74px 118px;
  align-items: center;
  gap: 10px;
  min-height: clamp(36px, 4.1vh, 47px);
  padding: 4px 8px;
  border-bottom: 1px solid rgba(78, 157, 210, 0.09);
  transition: background 0.35s ease, box-shadow 0.35s ease;
}
.rank-row::before {
  content: '';
  position: absolute;
  top: 15%;
  bottom: 15%;
  left: 0;
  width: 2px;
  border-radius: 2px;
  background: var(--row-accent, transparent);
  opacity: 0;
  transition: opacity 0.3s;
}
.rank-row--1, .rank-row--2, .rank-row--3 { flex-grow: 1.38; min-height: clamp(54px, 6.5vh, 76px); }
.rank-row--1 { --row-accent: #ffd166; background: linear-gradient(90deg, rgba(255, 196, 71, 0.13), rgba(255, 196, 71, 0.02) 58%, transparent); }
.rank-row--2 { --row-accent: #b8dcff; background: linear-gradient(90deg, rgba(147, 205, 255, 0.08), transparent 58%); }
.rank-row--3 { --row-accent: #ffad72; background: linear-gradient(90deg, rgba(255, 143, 84, 0.07), transparent 58%); }
.rank-row--1::before, .rank-row--2::before, .rank-row--3::before { opacity: 1; }
.rank-row.is-gain { background-color: rgba(82, 255, 188, 0.1); box-shadow: inset 0 0 30px rgba(68, 255, 183, 0.06); }
.rank-row.is-loss { background-color: rgba(255, 72, 125, 0.1); box-shadow: inset 0 0 30px rgba(255, 72, 125, 0.06); }

.rank-cell { position: relative; display: flex; align-items: center; gap: 6px; min-height: 1.4em; }
.rank-number { color: #6683a2; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: clamp(0.85rem, 1.2vw, 1.12rem); letter-spacing: 0.04em; }
.rank-row--1 .rank-number { color: #ffd166; font-size: clamp(1.15rem, 1.8vw, 1.7rem); text-shadow: 0 0 16px rgba(255, 196, 71, 0.42); }
.rank-row--2 .rank-number { color: #c9eaff; }
.rank-row--3 .rank-number { color: #ffb27e; }
.crown { color: #ffd166; filter: drop-shadow(0 0 8px rgba(255, 198, 68, 0.6)); }
.rank-arrow { position: absolute; right: 0; bottom: -7px; font-family: ui-monospace, monospace; font-size: 9px; }
.rank-arrow--up { color: #65ffc4; }
.rank-arrow--down { color: #ff6f9d; }

.team-cell { min-width: 0; }
.team-name { display: flex; align-items: baseline; gap: 8px; min-width: 0; }
.team-name strong { overflow: hidden; color: #dff8ff; font-size: clamp(0.78rem, 1.1vw, 1rem); font-weight: 650; letter-spacing: 0.04em; text-overflow: ellipsis; white-space: nowrap; }
.rank-row--1 .team-name strong { color: #fff4cf; text-shadow: 0 0 16px rgba(255, 210, 112, 0.26); }
.team-name span, .team-sub { color: #5c7a99; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 8px; letter-spacing: 0.08em; white-space: nowrap; }
.team-sub { margin-top: 2px; }
.score-track { height: 3px; margin-top: 5px; overflow: hidden; border-radius: 3px; background: rgba(80, 142, 190, 0.15); }
.score-track i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, rgba(44, 205, 255, 0.65), #6dfcff); box-shadow: 0 0 10px rgba(76, 238, 255, 0.5); transition: width 0.8s cubic-bezier(0.2, 0.75, 0.25, 1); }
.rank-row--1 .score-track i { background: linear-gradient(90deg, rgba(255, 180, 54, 0.65), #ffe59c); box-shadow: 0 0 10px rgba(255, 203, 85, 0.45); }

.combat-cell { display: flex; align-items: center; gap: 10px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 10px; }
.stat-up { display: inline-flex; align-items: center; gap: 3px; color: #62f6c5; }
.stat-down { color: #ff759e; }

.service-cell { display: flex; align-items: center; gap: 5px; }
.service-dot { width: 7px; height: 7px; border-radius: 50%; background: #7994ad; box-shadow: 0 0 7px currentColor; }
.service-dot.tone-success { background: #56f8bd; box-shadow: 0 0 8px rgba(86, 248, 189, 0.7); }
.service-dot.tone-danger { background: #ff5c8b; box-shadow: 0 0 8px rgba(255, 92, 139, 0.7); }
.service-dot.tone-warning { background: #ffbc5f; box-shadow: 0 0 8px rgba(255, 188, 95, 0.7); }
.service-dot.tone-info { background: #59d9ff; box-shadow: 0 0 8px rgba(89, 217, 255, 0.7); }

.score-cell { position: relative; color: #f2ffff; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: clamp(1rem, 1.55vw, 1.45rem); font-weight: 500; text-align: right; text-shadow: 0 0 14px rgba(84, 238, 255, 0.28); }
.rank-row--1 .score-cell { color: #ffe8a6; font-size: clamp(1.35rem, 2.15vw, 2rem); text-shadow: 0 0 18px rgba(255, 205, 95, 0.4); }
.score-delta { position: absolute; top: -4px; right: 0; padding: 1px 5px; border-radius: 4px; font-family: ui-monospace, monospace; font-size: 9px; font-weight: 600; letter-spacing: 0.04em; animation: delta-rise 0.75s ease-out; }
.score-delta--up { color: #76ffd0; background: rgba(46, 255, 188, 0.13); }
.score-delta--down { color: #ff88ab; background: rgba(255, 72, 125, 0.13); }

.ranking-empty { display: flex; flex: 1; align-items: center; justify-content: center; gap: 8px; color: #5e7b99; font-family: ui-monospace, monospace; font-size: 11px; letter-spacing: 0.08em; }
.ranking-empty svg { opacity: 0.65; }

.side-panel { display: grid; grid-template-rows: auto minmax(170px, 220px) minmax(0, 1fr) auto; gap: clamp(10px, 1.2vh, 15px); min-height: 0; }
.stat-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.stat-card { position: relative; display: flex; flex-direction: column; gap: 2px; min-height: 86px; padding: 10px 12px; overflow: hidden; border: 1px solid rgba(83, 196, 255, 0.14); border-radius: 11px; background: linear-gradient(145deg, rgba(12, 30, 54, 0.82), rgba(5, 14, 28, 0.7)); }
.stat-card::after { content: ''; position: absolute; right: -20px; bottom: -28px; width: 72px; height: 72px; border-radius: 50%; background: currentColor; opacity: 0.07; filter: blur(4px); }
.stat-card svg { color: #5bdfff; opacity: 0.9; }
.stat-card span { color: #6d8aa8; font-size: 9px; letter-spacing: 0.12em; }
.stat-card strong { color: #f0ffff; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: clamp(1.35rem, 2vw, 1.9rem); font-weight: 500; line-height: 1; }
.stat-card strong em { margin-left: 1px; color: #6f91ae; font-size: 0.45em; font-style: normal; }
.stat-card small { color: #516e8b; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 7px; letter-spacing: 0.1em; }
.stat-card--teams { color: #5bdfff; }
.stat-card--attack { color: #8dffbd; }
.stat-card--breach { color: #ffce72; }
.stat-card--round { color: #c69cff; }
.stat-card--teams strong { color: #b7f7ff; }
.stat-card--attack strong { color: #baffd6; }
.stat-card--breach strong { color: #ffe3a0; }
.stat-card--round strong { color: #e2ceff; }

.feed-panel, .notice-panel { display: flex; flex-direction: column; padding: clamp(10px, 1.4vh, 16px) clamp(11px, 1.2vw, 16px); min-height: 0; }
.radar-panel { display: flex; flex-direction: column; padding: clamp(9px, 1.2vh, 14px) clamp(11px, 1.2vw, 16px) 4px; min-height: 0; }
.radar-panel .panel-side { color: #5d7d9b; }
.radar-body { display: grid; flex: 1; grid-template-columns: minmax(0, 1fr) 154px; gap: 8px; min-height: 0; }
.radar-legend { display: flex; flex-direction: column; justify-content: center; gap: 5px; min-width: 0; margin: 0; padding: 0 2px 0 0; list-style: none; }
.radar-legend li { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; align-items: baseline; gap: 5px; min-width: 0; padding-bottom: 4px; border-bottom: 1px solid rgba(74, 146, 200, 0.08); }
.radar-legend span { color: #5e7d9c; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 8px; }
.radar-legend strong { overflow: hidden; color: #a5c6dc; font-size: 9px; font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.radar-legend em { color: #76e8ff; font-family: ui-monospace, monospace; font-size: 9px; font-style: normal; }
.radar-legend--1 span, .radar-legend--1 em { color: #ffd166; }
.radar-legend--1 strong { color: #ffe9ab; }
.radar-legend--2 span { color: #c9eaff; }
.radar-legend--3 span { color: #ffb27e; }
.feed-count, .notice-count { display: grid; place-items: center; min-width: 22px; height: 20px; padding: 0 5px; border: 1px solid rgba(95, 220, 255, 0.2); border-radius: 5px; color: #70dfff; font-family: ui-monospace, monospace; font-size: 9px; }
.feed-list { flex: 1; min-height: 0; margin: 8px 0 0; padding: 0; overflow: auto; list-style: none; scrollbar-width: none; }
.feed-list::-webkit-scrollbar { display: none; }
.feed-item { display: grid; grid-template-columns: 54px minmax(0, 1fr) 8px; align-items: center; gap: 8px; min-height: 32px; padding: 5px 0; border-bottom: 1px solid rgba(74, 146, 200, 0.08); }
.feed-time { color: #536f8c; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 8px; letter-spacing: 0.02em; }
.feed-copy { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.feed-copy strong { overflow: hidden; color: #cfefff; font-size: 10px; font-weight: 550; text-overflow: ellipsis; white-space: nowrap; }
.feed-copy small { overflow: hidden; color: #607e9c; font-size: 9px; text-overflow: ellipsis; white-space: nowrap; }
.feed-node { width: 5px; height: 5px; border-radius: 50%; background: #6be7ff; box-shadow: 0 0 8px currentColor; }
.feed-item--up .feed-copy strong, .feed-item--up .feed-node { color: #6dffc6; }
.feed-item--up .feed-node { background: currentColor; }
.feed-item--down .feed-copy strong, .feed-item--down .feed-node { color: #ff7fa7; }
.feed-item--down .feed-node { background: currentColor; }
.feed-item--warn .feed-copy strong, .feed-item--warn .feed-node { color: #ffd166; }
.feed-item--warn .feed-node { background: currentColor; }

.notice-feature { margin-top: 9px; padding: 10px 11px; border: 1px solid rgba(83, 196, 255, 0.14); border-left: 2px solid #5ce7ff; border-radius: 8px; background: rgba(18, 53, 82, 0.28); }
.notice-feature--warning { border-left-color: #ffd166; }
.notice-feature--critical { border-left-color: #ff6b9d; }
.notice-top { display: flex; align-items: center; gap: 7px; }
.notice-level { padding: 1px 5px; border-radius: 3px; color: #7ee9ff; background: rgba(72, 219, 255, 0.1); font-family: ui-monospace, monospace; font-size: 8px; letter-spacing: 0.05em; }
.notice-feature--warning .notice-level { color: #ffd166; background: rgba(255, 196, 71, 0.1); }
.notice-feature--critical .notice-level { color: #ff86ab; background: rgba(255, 92, 139, 0.1); }
.pin-mark { color: #ffcf70; font-family: ui-monospace, monospace; font-size: 7px; letter-spacing: 0.1em; }
.notice-top time { margin-left: auto; color: #566f89; font-family: ui-monospace, monospace; font-size: 8px; }
.notice-feature h3 { margin: 6px 0 3px; overflow: hidden; color: #e0f8ff; font-size: 11px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.notice-feature p { display: -webkit-box; margin: 0; overflow: hidden; color: #7593b0; font-size: 9px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.notice-list { margin: 7px 0 0; padding: 0; list-style: none; }
.notice-list li { display: flex; align-items: center; gap: 7px; min-height: 21px; overflow: hidden; }
.notice-list span { flex: 0 0 auto; color: #5d87a4; font-family: ui-monospace, monospace; font-size: 7px; }
.notice-list strong { overflow: hidden; color: #8eabc3; font-size: 9px; font-weight: 400; text-overflow: ellipsis; white-space: nowrap; }
.notice-empty { margin: 12px 0 0; color: #5c7894; font-size: 10px; }

.bs-footer {
  position: relative;
  z-index: 3;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  min-height: 30px;
  padding-top: 8px;
  border-top: 1px solid rgba(82, 200, 255, 0.14);
}
.ticker-label { display: inline-flex; align-items: center; gap: 5px; color: #64e5ff; font-family: ui-monospace, monospace; font-size: 9px; letter-spacing: 0.12em; white-space: nowrap; }
.ticker-window { overflow: hidden; mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent); }
.ticker-track { display: flex; width: max-content; gap: 44px; color: #7fa0ba; font-size: 9px; letter-spacing: 0.04em; white-space: nowrap; animation: ticker 38s linear infinite; }
.ticker-track span { padding-right: 44px; }
.footer-sync { display: flex; align-items: center; gap: 12px; color: #5c7b99; font-family: ui-monospace, monospace; font-size: 8px; letter-spacing: 0.08em; white-space: nowrap; }

.error-strip { position: absolute; right: 2.4vw; bottom: 50px; z-index: 12; max-width: 60vw; padding: 6px 10px; border: 1px solid rgba(255, 100, 130, 0.35); border-radius: 6px; color: #ff9cb7; background: rgba(66, 13, 30, 0.84); font-size: 10px; }

.boot-overlay { position: absolute; inset: 0; z-index: 20; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; background: rgba(3, 7, 15, 0.88); backdrop-filter: blur(8px); }
.boot-mark { color: #dbffff; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: clamp(1.4rem, 3vw, 2.6rem); letter-spacing: 0.16em; text-shadow: 0 0 26px rgba(83, 238, 255, 0.5); }
.boot-mark span { color: #6a8cff; }
.boot-overlay p { margin: 0; color: #6e8ba7; font-family: ui-monospace, monospace; font-size: 10px; letter-spacing: 0.12em; }
.boot-ring { width: 46px; height: 46px; border: 1px solid rgba(79, 226, 255, 0.25); border-top-color: #63efff; border-radius: 50%; animation: spin 1.2s linear infinite; box-shadow: 0 0 24px rgba(83, 238, 255, 0.18); }
.boot-overlay--error { color: #ff9db8; }
.boot-retry { padding: 6px 12px; border: 1px solid rgba(92, 220, 255, 0.3); border-radius: 5px; color: #9fefff; background: rgba(16, 50, 75, 0.65); font-size: 10px; cursor: pointer; }
.boot-retry:hover { border-color: #75f2ff; }

.rank-move, .rank-enter-active, .rank-leave-active { transition: transform 0.62s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.4s ease; }
.rank-enter-from, .rank-leave-to { opacity: 0; transform: translateY(10px) scale(0.98); }
.feed-move, .feed-enter-active, .feed-leave-active { transition: transform 0.35s ease, opacity 0.25s ease; }
.feed-enter-from, .feed-leave-to { opacity: 0; transform: translateY(-6px); }

@keyframes ambient-drift { from { transform: translate3d(0, 0, 0) scale(1); } to { transform: translate3d(4vw, 3vh, 0) scale(1.12); } }
@keyframes grid-drift { from { background-position: 0 0, 0 0; } to { background-position: 64px 64px, 64px 64px; } }
@keyframes scan { from { transform: translateY(0); } to { transform: translateY(580%); } }
@keyframes pulse { 0%, 100% { opacity: 0.45; transform: scale(0.85); } 50% { opacity: 1; transform: scale(1.15); } }
@keyframes delta-rise { from { opacity: 0; transform: translateY(6px); } 30% { opacity: 1; transform: translateY(0); } to { opacity: 0.9; transform: translateY(-2px); } }
@keyframes ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 1180px) {
  .bs-header { grid-template-columns: minmax(150px, 0.8fr) auto minmax(260px, 1fr); }
  .brand-copy span { display: none; }
  .bs-body { grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.9fr); }
  .ranking-head, .rank-row { grid-template-columns: 50px minmax(0, 1fr) 82px 62px 100px; }
}
@media (max-height: 860px) {
  .bigscreen { gap: 8px; padding-top: 10px; padding-bottom: 10px; }
  .bs-header { min-height: 62px; }
  .brand-mark { width: 46px; height: 46px; }
  .match-block h1 { margin-top: 4px; font-size: clamp(1rem, 1.8vw, 1.55rem); }
  .rank-row { min-height: 28px; padding-top: 3px; padding-bottom: 3px; }
  .rank-row--1, .rank-row--2, .rank-row--3 { min-height: 40px; }
  .team-sub { display: none; }
  .score-track { height: 2px; margin-top: 3px; }
  .stat-card { min-height: 68px; padding: 7px 10px; }
  .stat-card strong { font-size: 1.25rem; }
  .radar-panel { display: none; }
  .side-panel { grid-template-rows: auto minmax(0, 1fr) auto; }
  .bs-footer { min-height: 24px; }
}
@media (max-height: 760px) {
  .rank-row { min-height: 24px; }
  .rank-row--1, .rank-row--2, .rank-row--3 { min-height: 34px; }
  .notice-panel { display: none; }
  .side-panel { grid-template-rows: auto minmax(0, 1fr); }
}
@media (prefers-reduced-motion: reduce) {
  .ambient, .grid-overlay, .scanline, .status-pulse, .boot-ring, .ticker-track, .score-delta { animation: none !important; }
  .rank-move, .rank-enter-active, .rank-leave-active, .feed-move, .feed-enter-active, .feed-leave-active, .score-track i { transition: none !important; }
}

/* Blue-white projector theme */
.bigscreen {
  --bs-ink: #0b2a5b;
  --bs-muted: #5a7aa3;
  --bs-accent: #1f63d6;
  --bs-line: rgba(31, 99, 214, 0.17);
  color: var(--bs-ink);
  background:
    radial-gradient(circle at 14% -12%, rgba(80, 150, 255, 0.18), transparent 36%),
    radial-gradient(circle at 88% 4%, rgba(70, 135, 220, 0.12), transparent 34%),
    linear-gradient(180deg, #f5faff, #e5f1ff);
  background-size: cover;
  background-position: center;
}
.bigscreen::after { background: radial-gradient(ellipse at center, transparent 52%, rgba(31, 99, 214, 0.1) 100%); }
.ambient { opacity: 0.2; }
.ambient--cyan { background: #2f80ed; }
.ambient--violet { background: #8ec5ff; }
.grid-overlay {
  opacity: 0.55;
  background-image:
    linear-gradient(rgba(31, 99, 214, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(31, 99, 214, 0.08) 1px, transparent 1px);
}
.scanline { background: linear-gradient(to bottom, transparent, rgba(31, 99, 214, 0.07), transparent); }

.brand-mark {
  border-color: rgba(31, 99, 214, 0.42);
  color: var(--bs-accent);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.9), rgba(220, 238, 255, 0.8));
  box-shadow: inset 0 0 24px rgba(31, 99, 214, 0.08), 0 0 28px rgba(31, 99, 214, 0.08);
}
.brand-mark--logo { display: block; padding: 5px; border-radius: 50%; background: #ffffff; object-fit: contain; }
.brand-copy span, .match-code { color: #5478a5; }
.match-block h1 { color: var(--bs-ink); text-shadow: 0 0 24px rgba(31, 99, 214, 0.14); }
.match-meta { color: #4f719b; }
.match-meta b { color: var(--bs-accent); }
.frozen-label, .demo-chip { color: var(--bs-accent); }
.demo-chip { border-color: rgba(31, 99, 214, 0.35); }
.tone-success, .live-chip { color: #1f63d6; }
.tone-warning { color: #2f80ed; }
.tone-danger { color: #0b2a5b; }
.tone-info { color: #1f63d6; }
.tone-neutral { color: #6c87a8; }
.live-chip.is-offline { color: #0b2a5b; }
.clock-block span { color: #5a7ca4; }
.clock-block strong { color: var(--bs-ink); text-shadow: 0 0 18px rgba(31, 99, 214, 0.15); }
.icon-action {
  border-color: rgba(31, 99, 214, 0.22);
  color: #2f5f96;
  background: rgba(255, 255, 255, 0.58);
}
.icon-action:hover { color: var(--bs-accent); border-color: rgba(31, 99, 214, 0.55); background: #ffffff; }

.panel {
  border-color: rgba(31, 99, 214, 0.22);
  background: linear-gradient(155deg, rgba(255, 255, 255, 0.97), rgba(240, 247, 255, 0.92));
  box-shadow: inset 0 1px 0 #fff, 0 20px 60px rgba(13, 52, 107, 0.12);
}
.panel::before { background: linear-gradient(90deg, transparent, rgba(31, 99, 214, 0.5), transparent); }
.eyebrow, .rank-count { color: var(--bs-accent); }
.panel-title h2 { color: var(--bs-ink); }
.panel-side { color: #6c87a8; }
.ranking-head { border-bottom-color: var(--bs-line); color: #5a7ca4; }
.rank-row { border-bottom-color: rgba(31, 99, 214, 0.1); }
.rank-row--1 { --row-accent: #1f63d6; background: linear-gradient(90deg, rgba(31, 99, 214, 0.14), rgba(31, 99, 214, 0.03) 58%, transparent); }
.rank-row--2 { --row-accent: #4f8fe8; background: linear-gradient(90deg, rgba(79, 143, 232, 0.1), transparent 58%); }
.rank-row--3 { --row-accent: #78aef0; background: linear-gradient(90deg, rgba(120, 174, 240, 0.09), transparent 58%); }
.rank-row.is-gain { background-color: rgba(31, 99, 214, 0.1); box-shadow: inset 0 0 30px rgba(31, 99, 214, 0.05); }
.rank-row.is-loss { background-color: rgba(11, 42, 91, 0.08); box-shadow: inset 0 0 30px rgba(11, 42, 91, 0.04); }
.rank-number { color: #6c87a8; }
.rank-row--1 .rank-number { color: #1f63d6; text-shadow: 0 0 16px rgba(31, 99, 214, 0.2); }
.rank-row--2 .rank-number { color: #4f8fe8; }
.rank-row--3 .rank-number { color: #78aef0; }
.crown { color: #1f63d6; filter: drop-shadow(0 0 8px rgba(31, 99, 214, 0.35)); }
.rank-arrow--up { color: #1f63d6; }
.rank-arrow--down { color: #0b2a5b; }
.team-name strong { color: var(--bs-ink); }
.rank-row--1 .team-name strong { color: #0b2a5b; text-shadow: 0 0 16px rgba(31, 99, 214, 0.12); }
.team-name span, .team-sub { color: #6c87a8; }
.score-track { background: rgba(31, 99, 214, 0.12); }
.score-track i { background: linear-gradient(90deg, #4f8fe8, #8ec5ff); box-shadow: 0 0 10px rgba(31, 99, 214, 0.28); }
.rank-row--1 .score-track i { background: linear-gradient(90deg, #1f63d6, #8ec5ff); box-shadow: 0 0 10px rgba(31, 99, 214, 0.3); }
.stat-up { color: #1f63d6; }
.stat-down { color: #0b2a5b; }
.service-dot { background: #6c87a8; }
.service-dot.tone-success { background: #1f63d6; box-shadow: 0 0 8px rgba(31, 99, 214, 0.5); }
.service-dot.tone-danger { background: #0b2a5b; box-shadow: 0 0 8px rgba(11, 42, 91, 0.45); }
.service-dot.tone-warning { background: #2f80ed; box-shadow: 0 0 8px rgba(47, 128, 237, 0.5); }
.service-dot.tone-info { background: #4f8fe8; box-shadow: 0 0 8px rgba(79, 143, 232, 0.5); }
.score-cell { color: var(--bs-ink); text-shadow: 0 0 14px rgba(31, 99, 214, 0.1); }
.rank-row--1 .score-cell { color: #1f63d6; text-shadow: 0 0 18px rgba(31, 99, 214, 0.16); }
.score-delta--up { color: #1f63d6; background: rgba(31, 99, 214, 0.1); }
.score-delta--down { color: #0b2a5b; background: rgba(11, 42, 91, 0.08); }
.ranking-empty { color: #6c87a8; }

.stat-card {
  border-color: var(--bs-line);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(237, 246, 255, 0.84));
}
.stat-card svg { color: #1f63d6; opacity: 0.82; }
.stat-card span { color: #5a7ca4; }
.stat-card strong { color: var(--bs-ink); }
.stat-card strong em { color: #6c87a8; }
.stat-card small { color: #6c87a8; }
.stat-card--teams { color: #1f63d6; }
.stat-card--attack { color: #2f80ed; }
.stat-card--breach { color: #4f8fe8; }
.stat-card--round { color: #78aef0; }
.stat-card--teams strong { color: #1f63d6; }
.stat-card--attack strong { color: #2f80ed; }
.stat-card--breach strong { color: #4f8fe8; }
.stat-card--round strong { color: #78aef0; }

.radar-panel .panel-side { color: #6c87a8; }
.radar-legend li { border-bottom-color: rgba(31, 99, 214, 0.1); }
.radar-legend span { color: #6c87a8; }
.radar-legend strong { color: #315b8f; }
.radar-legend em { color: #1f63d6; }
.radar-legend--1 span, .radar-legend--1 em { color: #1f63d6; }
.radar-legend--1 strong { color: #0b2a5b; }
.radar-legend--2 span { color: #4f8fe8; }
.radar-legend--3 span { color: #78aef0; }

.feed-count, .notice-count { border-color: rgba(31, 99, 214, 0.2); color: #1f63d6; }
.feed-item { border-bottom-color: rgba(31, 99, 214, 0.1); }
.feed-time { color: #6c87a8; }
.feed-copy strong { color: var(--bs-ink); }
.feed-copy small { color: #4f719b; }
.feed-node { background: #1f63d6; }
.feed-item--up .feed-copy strong, .feed-item--up .feed-node { color: #1f63d6; }
.feed-item--down .feed-copy strong, .feed-item--down .feed-node { color: #0b2a5b; }
.feed-item--warn .feed-copy strong, .feed-item--warn .feed-node { color: #2f80ed; }

.notice-feature { border-color: var(--bs-line); border-left-color: #1f63d6; background: rgba(255, 255, 255, 0.8); }
.notice-feature--warning { border-left-color: #2f80ed; }
.notice-feature--critical { border-left-color: #0b2a5b; }
.notice-level { color: #1f63d6; background: rgba(31, 99, 214, 0.08); }
.notice-feature--warning .notice-level { color: #2f80ed; background: rgba(47, 128, 237, 0.08); }
.notice-feature--critical .notice-level { color: #0b2a5b; background: rgba(11, 42, 91, 0.08); }
.pin-mark { color: #1f63d6; }
.notice-top time { color: #6c87a8; }
.notice-feature h3 { color: var(--bs-ink); }
.notice-feature p { color: #3f628c; }
.notice-list span { color: #6c87a8; }
.notice-list strong { color: #315b8f; }
.notice-empty { color: #6c87a8; }

.bs-footer { border-top-color: var(--bs-line); }
.ticker-label { color: #1f63d6; }
.ticker-track { color: #5a7ca4; }
.footer-sync { color: #6c87a8; }
.error-strip { border-color: rgba(31, 99, 214, 0.35); color: #0b2a5b; background: rgba(232, 242, 255, 0.96); }
.boot-overlay { background: rgba(238, 245, 255, 0.92); }
.boot-mark { color: var(--bs-ink); text-shadow: 0 0 26px rgba(31, 99, 214, 0.16); }
.boot-mark span { color: #1f63d6; }
.boot-overlay p { color: #5a7ca4; }
.boot-ring { border-color: rgba(31, 99, 214, 0.2); border-top-color: #1f63d6; box-shadow: 0 0 24px rgba(31, 99, 214, 0.1); }
.boot-overlay--error { color: #0b2a5b; }
.boot-retry { border-color: rgba(31, 99, 214, 0.32); color: #1f63d6; background: rgba(255, 255, 255, 0.8); }
.boot-retry:hover { border-color: #1f63d6; }
</style>
