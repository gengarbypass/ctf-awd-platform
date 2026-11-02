<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Activity, Bell, ChevronDown, ClipboardList, Flag, Gauge, LogOut, Menu, MonitorCog,
  ScrollText, ShieldCheck, Swords, Trophy, Users, X, Boxes,
} from '@lucide/vue'
import { isDemo } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useMatchStore } from '@/stores/match'
import { formatDuration, matchStatus } from '@/utils/format'
import StatusTag from '@/components/StatusTag.vue'

const auth = useAuthStore()
const matchStore = useMatchStore()
const router = useRouter()
const mobileOpen = ref(false)
const playerNav = [
  { to: '/dashboard', label: '训练首页', icon: Gauge },
  { to: '/scoreboard', label: '实时计分板', icon: Trophy },
  { to: '/targets', label: '我的靶机', icon: MonitorCog },
  { to: '/submissions', label: '提交记录', icon: ClipboardList },
  { to: '/announcements', label: '公告', icon: Bell },
]
const adminNav = [
  { to: '/admin', label: '运行总览', icon: Gauge },
  { to: '/admin/match', label: '比赛控制', icon: Flag },
  { to: '/admin/services', label: '服务模板', icon: Boxes },
  { to: '/admin/teams', label: '队伍管理', icon: Users },
  { to: '/admin/users', label: '选手管理', icon: ShieldCheck },
  { to: '/admin/targets', label: '靶机管理', icon: MonitorCog },
  { to: '/admin/submissions', label: '提交与流水', icon: ClipboardList },
  { to: '/admin/announcements', label: '公告管理', icon: Bell },
  { to: '/admin/audit', label: '审计日志', icon: ScrollText },
]
const navItems = computed(() => auth.isAdmin ? adminNav : playerNav)
const matchMeta = computed(() => matchStore.match ? matchStatus[matchStore.match.status] : null)

async function logout() { await auth.logout(); await router.replace('/login') }
function closeOnEscape(event: KeyboardEvent) { if (event.key === 'Escape') mobileOpen.value = false }
watch(() => auth.user?.id, async id => {
  if (!id) return
  try { await matchStore.load() } catch (error) { console.error('比赛状态加载失败', error) }
}, { immediate: true })
onMounted(() => {
  matchStore.startClock()
  window.addEventListener('keydown', closeOnEscape)
})
onBeforeUnmount(() => { matchStore.stopClock(); window.removeEventListener('keydown', closeOnEscape) })
</script>

<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳至主要内容</a>
    <button v-if="mobileOpen" class="sidebar-backdrop" type="button" aria-label="关闭导航" @click="mobileOpen = false" />
    <aside class="sidebar" :class="{ 'is-open': mobileOpen }" aria-label="主导航">
      <div class="brand">
        <RouterLink :to="auth.isAdmin ? '/admin' : '/dashboard'" class="brand__link" aria-label="塔大网安师市行首页" @click="mobileOpen = false">
          <span class="brand__mark" aria-hidden="true">塔</span>
          <span><strong>塔大网安</strong><small>师市行实战平台</small></span>
        </RouterLink>
        <button class="icon-button sidebar-close" type="button" aria-label="关闭导航" @click="mobileOpen = false"><X :size="20" aria-hidden="true" /></button>
      </div>
      <div class="sidebar-context"><Swords :size="17" aria-hidden="true" /><span>{{ auth.isAdmin ? '竞赛管理' : '授权内部训练' }}</span></div>
      <nav class="sidebar-nav">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item" active-class="is-active" @click="mobileOpen = false"><component :is="item.icon" :size="18" aria-hidden="true" /><span>{{ item.label }}</span></RouterLink>
        <RouterLink v-if="auth.isAdmin" to="/scoreboard" class="nav-item nav-item--secondary" active-class="is-active" @click="mobileOpen = false"><Trophy :size="18" aria-hidden="true" /><span>公开计分板</span></RouterLink>
      </nav>
      <div class="sidebar-foot">
        <span>每队初始分 1000</span><span>攻击 +100 / 防守 -50</span>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="topbar__left"><button class="icon-button mobile-menu" type="button" aria-label="打开导航" @click="mobileOpen = true"><Menu :size="21" aria-hidden="true" /></button><div class="match-identity"><strong>{{ matchStore.match?.name || (matchStore.loading ? '正在读取比赛' : '暂无比赛') }}</strong><span v-if="isDemo" class="demo-label">演示数据</span></div></div>
        <div class="topbar__right">
          <div v-if="matchStore.match && matchMeta" class="match-clock"><StatusTag :label="matchMeta.label" :tone="matchMeta.tone" /><span class="num">{{ ['RUNNING', 'PAUSED'].includes(matchStore.match.status) ? formatDuration(matchStore.remainingSeconds) : '00:00:00' }}</span></div>
          <el-dropdown trigger="click">
            <button class="user-menu" type="button"><span class="user-avatar" aria-hidden="true">{{ auth.user?.username.slice(0, 1).toUpperCase() }}</span><span class="user-copy"><strong>{{ auth.user?.username }}</strong><small>{{ auth.isAdmin ? '管理员' : auth.user?.team_name }}</small></span><ChevronDown :size="15" aria-hidden="true" /></button>
            <template #dropdown><el-dropdown-menu><el-dropdown-item @click="logout"><LogOut :size="15" aria-hidden="true" />退出登录</el-dropdown-item></el-dropdown-menu></template>
          </el-dropdown>
        </div>
      </header>
      <main id="main-content" class="main-content" tabindex="-1"><slot /></main>
      <footer class="app-footer"><span>仅限授权内部 CTF-AWD 训练</span><span><Activity :size="14" aria-hidden="true" />计分与靶机一体化核心节点</span></footer>
    </div>
  </div>
</template>
