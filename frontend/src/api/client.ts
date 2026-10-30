import { demo } from './demo'
import type {
  AdminOverview, Announcement, AnnouncementPayload, ApiResponse, AuditLog, FlagResult,
  LoginPayload, Match, RegisterPayload, Scoreboard, ScoreLedger, Submission, Target, Team,
  TeamPayload, User, UserPayload, HealthCheck,
} from './types'

export const isDemo = import.meta.env.DEV && import.meta.env.VITE_USE_DEMO !== 'false'
const apiBase = import.meta.env.VITE_API_BASE || '/api/v1'

export class ApiError extends Error {
  status: number
  code: string
  requestId?: string
  constructor(message: string, status = 500, code = 'ERROR', requestId?: string) {
    super(message)
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

async function request<T>(path: string, init: RequestInit = {}, demoCall: () => Promise<T>): Promise<T> {
  if (isDemo) return demoCall()
  let response: Response
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', ...init.headers },
    })
  } catch {
    throw new ApiError('无法连接平台服务，请检查网络后重试。', 0, 'NETWORK_ERROR')
  }
  const contentType = response.headers.get('content-type') ?? ''
  const body = contentType.includes('application/json') ? await response.json() as ApiResponse<T> : null
  if (!response.ok || !body) {
    throw new ApiError(body?.message || '请求未完成，请稍后重试。', response.status, body?.code || 'HTTP_ERROR', body?.request_id)
  }
  return body.data
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  login: (payload: LoginPayload) => request<User>('/auth/login', json('POST', payload), () => demo.login(payload)),
  register: (payload: RegisterPayload) => request<User>('/auth/register', json('POST', payload), () => demo.register(payload)),
  logout: () => request<null>('/auth/logout', json('POST'), () => demo.logout()),
  me: () => request<User>('/users/me', {}, () => demo.me()),
  match: () => request<Match>('/match/current', {}, () => demo.match()),
  scoreboard: () => request<Scoreboard>('/scoreboard', {}, () => demo.scoreboard()),
  targetsMine: () => request<Target[]>('/targets/mine', {}, () => demo.targetsMine()),
  submissionsMine: () => request<Submission[]>('/submissions/mine', {}, () => demo.submissionsMine()),
  announcements: () => request<Announcement[]>('/announcements', {}, () => demo.announcements()),
  submitFlag: (flag: string, requestId: string) => request<FlagResult>('/flags/submit', json('POST', { flag, request_id: requestId }), () => demo.submitFlag(flag)),
  restartTarget: (id: string) => request<Target>(`/targets/${id}/restart`, json('POST'), () => demo.restartTarget(id)),

  adminOverview: () => request<AdminOverview>('/admin/overview', {}, () => demo.overview()),
  adminTeams: () => request<Team[]>('/admin/teams', {}, () => demo.teams()),
  createTeam: (payload: TeamPayload) => request<Team>('/admin/teams', json('POST', payload), () => demo.createTeam(payload)),
  updateTeam: (id: string, payload: Partial<Team> & { reset_score?: boolean }) => request<Team>(`/admin/teams/${id}`, json('PUT', payload), () => demo.updateTeam(id, payload)),
  adminUsers: () => request<User[]>('/admin/users', {}, () => demo.users()),
  createUser: (payload: UserPayload) => request<User>('/admin/users', json('POST', payload), () => demo.createUser(payload)),
  updateUser: (id: string, payload: Partial<User> & { password?: string }) => request<User>(`/admin/users/${id}`, json('PUT', payload), () => demo.updateUser(id, payload)),
  matchAction: (action: 'start' | 'pause' | 'resume' | 'finish', body: Record<string, never> = {}) => request<Match>(`/admin/match/${action}`, json('POST', body), () => demo.matchAction(action)),
  readyMatch: () => request<Match>('/admin/match/ready', json('POST', {}), () => demo.matchAction('ready')),
  createMatch: (payload: Pick<Match, 'name' | 'starts_at' | 'ends_at' | 'round_seconds' | 'grace_seconds'>) => request<Match>('/admin/matches', json('POST', payload), () => demo.createMatch(payload)),
  freezeMatch: (frozen: boolean) => request<Match>('/admin/match/freeze', json('POST', { frozen }), () => demo.matchAction('freeze')),
  updateMatch: (payload: Partial<Match>) => request<Match>('/admin/match', json('PUT', payload), () => demo.updateMatch(payload)),
  adminTargets: () => request<Target[]>('/admin/targets', {}, () => demo.targets()),
  initializeTargets: () => request<unknown>('/admin/targets', json('POST', {}), () => demo.initializeTargets()),
  startTarget: (id: string) => request<Target>(`/admin/targets/${id}/start`, json('POST', {}), () => demo.changeTargetState(id, 'start')),
  stopTarget: (id: string) => request<Target>(`/admin/targets/${id}/stop`, json('POST', {}), () => demo.changeTargetState(id, 'stop')),
  healthRecords: (id: string) => request<HealthCheck[]>(`/admin/health?target_id=${encodeURIComponent(id)}`, {}, () => demo.healthRecords(id)),
  adminSubmissions: () => request<Submission[]>('/admin/submissions', {}, () => demo.submissions()),
  adminLedger: () => request<ScoreLedger[]>('/admin/scores/ledger', {}, () => demo.ledger()),
  adjustScore: (teamId: string, delta: number, reason: string) => request<ScoreLedger>('/admin/scores/adjust', json('POST', { team_id: teamId, delta, reason }), () => demo.adjustScore(teamId, delta, reason)),
  adminAnnouncements: () => request<Announcement[]>('/admin/announcements', {}, () => demo.announcements(true)),
  createAnnouncement: (payload: AnnouncementPayload) => request<Announcement>('/admin/announcements', json('POST', { ...payload, is_pinned: payload.pinned }), () => demo.createAnnouncement(payload)),
  updateAnnouncement: (id: string, payload: Partial<Announcement>) => request<Announcement>(`/admin/announcements/${id}`, json('PUT', { ...payload, is_pinned: payload.pinned }), () => demo.updateAnnouncement(id, payload)),
  adminAudit: () => request<AuditLog[]>('/admin/audit-logs', {}, () => demo.auditLogs()),
  exportScores: async () => {
    if (isDemo) return demo.exportScores()
    const response = await fetch(`${apiBase}/admin/scores/export`, { credentials: 'include' })
    if (!response.ok) throw new ApiError('成绩导出失败，请稍后重试。', response.status)
    return response.blob()
  },
}

export function createEventSource(onEvent: () => void, onState: (connected: boolean) => void) {
  if (isDemo) {
    onState(true)
    const timer = window.setInterval(onEvent, 5000)
    return () => { window.clearInterval(timer); onState(false) }
  }
  const source = new EventSource(`${apiBase}/scoreboard/events`, { withCredentials: true })
  const refresh = () => onEvent()
  source.addEventListener('score.changed', refresh)
  source.addEventListener('target.status', refresh)
  source.addEventListener('announcement.published', refresh)
  source.onopen = () => { onState(true); onEvent() }
  source.onerror = () => onState(false)
  return () => source.close()
}
