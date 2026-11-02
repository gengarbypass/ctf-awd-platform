import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isDemo } from '@/api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true, title: '登录' } },
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '训练首页', role: 'PLAYER' } },
    { path: '/scoreboard', component: () => import('@/views/ScoreboardView.vue'), meta: { title: '实时计分板' } },
    { path: '/screen', component: () => import('@/views/BigScreenView.vue'), meta: { title: '计分大屏', bare: true } },
    { path: '/targets', component: () => import('@/views/TargetsView.vue'), meta: { title: '我的靶机', role: 'PLAYER' } },
    { path: '/submissions', component: () => import('@/views/SubmissionsView.vue'), meta: { title: '提交记录', role: 'PLAYER' } },
    { path: '/announcements', component: () => import('@/views/AnnouncementsView.vue'), meta: { title: '公告' } },
    { path: '/admin', component: () => import('@/views/admin/AdminDashboardView.vue'), meta: { title: '运行总览', role: 'ADMIN' } },
    { path: '/admin/teams', component: () => import('@/views/admin/AdminTeamsView.vue'), meta: { title: '队伍管理', role: 'ADMIN' } },
    { path: '/admin/users', component: () => import('@/views/admin/AdminUsersView.vue'), meta: { title: '选手管理', role: 'ADMIN' } },
    { path: '/admin/match', component: () => import('@/views/admin/AdminMatchView.vue'), meta: { title: '比赛控制', role: 'ADMIN' } },
    { path: '/admin/services', component: () => import('@/views/admin/AdminServicesView.vue'), meta: { title: '服务模板', role: 'ADMIN' } },
    { path: '/admin/targets', component: () => import('@/views/admin/AdminTargetsView.vue'), meta: { title: '靶机管理', role: 'ADMIN' } },
    { path: '/admin/submissions', component: () => import('@/views/admin/AdminSubmissionsView.vue'), meta: { title: '提交与流水', role: 'ADMIN' } },
    { path: '/admin/announcements', component: () => import('@/views/admin/AdminAnnouncementsView.vue'), meta: { title: '公告管理', role: 'ADMIN' } },
    { path: '/admin/audit', component: () => import('@/views/admin/AdminAuditView.vue'), meta: { title: '审计日志', role: 'ADMIN' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async to => {
  const auth = useAuthStore()
  await auth.restore()
  if (isDemo && !auth.user && (to.query.preview === 'player' || to.query.preview === 'admin')) {
    const admin = to.query.preview === 'admin'
    await auth.login({ username: admin ? 'admin' : 'player1', password: admin ? 'Admin123!' : 'Player123!' })
  }
  if (to.meta.public) return auth.user ? auth.home() : true
  if (!auth.user) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.role && auth.user.role !== to.meta.role) return auth.home()
  return true
})

router.afterEach(to => { document.title = `${String(to.meta.title || '实战平台')} | 塔大网安师市行` })
export default router
