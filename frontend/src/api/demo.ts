import type {
  AdminOverview, Announcement, AnnouncementPayload, AuditLog, FlagResult, LoginPayload,
  Match, RegisterPayload, Scoreboard, ScoreLedger, Service, ServicePayload, Submission, Target, Team, TeamPayload,
  User, UserPayload,
} from './types'

const now = () => new Date().toISOString()
const minutesFromNow = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString()
const uid = () => globalThis.crypto?.randomUUID?.() ?? `demo-${Date.now()}-${Math.random()}`
const clone = <T>(value: T): T => structuredClone(value)

const teamNames = ['白杨', '胡杨', '昆仑', '塔河', '天山', '丝路', '磐石', '绿洲', '凌云', '星火']
const attacks = [7, 6, 6, 5, 4, 3, 3, 2, 1, 0]
const breaches = [3, 4, 2, 5, 4, 3, 6, 2, 1, 2]

const teams: Team[] = teamNames.map((name, index) => ({
  id: `team-${index + 1}`,
  team_no: index + 1,
  name,
  invite_code: `TARC-${String(index + 1).padStart(2, '0')}-2026`,
  current_score: 1000 + attacks[index] * 100 - breaches[index] * 50,
  attack_count: attacks[index],
  breached_count: breaches[index],
  member_count: index % 3 === 0 ? 4 : 3,
  status: 'ACTIVE',
  unhealthy_seconds: index * 37,
  last_scored_at: minutesFromNow(-index * 4 - 2),
}))

const users: User[] = [
  { id: 'user-admin', username: 'admin', role: 'ADMIN', team_id: null, status: 'ACTIVE', last_login_at: minutesFromNow(-40) },
  { id: 'user-player', username: 'player1', role: 'PLAYER', team_id: 'team-1', team_name: '白杨', status: 'ACTIVE', last_login_at: minutesFromNow(-12) },
  { id: 'user-player2', username: 'player2', role: 'PLAYER', team_id: 'team-1', team_name: '白杨', status: 'ACTIVE', last_login_at: minutesFromNow(-18) },
  { id: 'user-player3', username: 'player3', role: 'PLAYER', team_id: 'team-2', team_name: '胡杨', status: 'ACTIVE', last_login_at: minutesFromNow(-25) },
]

const match: Match = {
  id: 'match-demo', name: '网安师市行实战对抗', status: 'RUNNING',
  starts_at: minutesFromNow(-118), ends_at: minutesFromNow(122), server_time: now(),
  round_seconds: 300, grace_seconds: 30, current_round: 24, score_frozen: false,
}

const serviceTemplates = [
  { code: 'web', name: 'Web 服务', protocol: 'HTTP', internal_port: 80 },
  { code: 'api', name: 'API 服务', protocol: 'TCP', internal_port: 8080 },
  { code: 'db', name: '数据库题服务', protocol: 'TCP', internal_port: 3306 },
]

const serviceCatalog: Service[] = serviceTemplates.map((service, index) => ({
  id: `service-${index + 1}`,
  code: service.code,
  name: service.name,
  service_no: index + 1,
  protocol: service.protocol as 'TCP' | 'HTTP',
  internal_port: service.internal_port,
  public_base_port: 20000 + index + 1,
  flag_path: '/data/flag',
  image: 'nginx:stable-alpine',
  check_config: service.protocol === 'HTTP' ? { path: '/', status: 200 } : {},
}))

const targets: Target[] = teams.flatMap((team, teamIndex) => serviceTemplates.map((service, serviceIndex) => ({
  id: `target-${team.team_no}-${serviceIndex + 1}`,
  team_id: team.id,
  team_no: team.team_no,
  team_name: team.name,
  service_id: `service-${serviceIndex + 1}`,
  service_code: service.code,
  service_name: service.name,
  protocol: service.protocol,
  attack_ip: `172.31.${team.team_no}.${serviceIndex + 1}`,
  public_port: 20000 + team.team_no * 100 + serviceIndex + 1,
  internal_port: service.internal_port,
  container_name: `target-t${String(team.team_no).padStart(2, '0')}-s0${serviceIndex + 1}`,
  status: teamIndex === 4 && serviceIndex === 1 ? 'UNHEALTHY' : teamIndex === 7 && serviceIndex === 0 ? 'RESTARTING' : 'RUNNING',
  last_checked_at: now(),
  restart_count: teamIndex === 7 && serviceIndex === 0 ? 1 : 0,
  error: teamIndex === 4 && serviceIndex === 1 ? '连续两次 TCP 检查失败' : null,
})))

const announcements: Announcement[] = [
  { id: 'notice-1', title: '第 24 轮 Flag 已轮换', content: '本轮 Flag 已写入全部正常靶机。上一周期 Flag 保留 30 秒提交宽限期。', level: 'INFO', published_at: minutesFromNow(-3), status: 'PUBLISHED', pinned: false },
  { id: 'notice-2', title: '第五队 API 服务正在恢复', content: '平台已发起受控重启，原数据卷保持不变。恢复期间不计额外分数。', level: 'WARNING', published_at: minutesFromNow(-11), status: 'PUBLISHED', pinned: true },
  { id: 'notice-3', title: '比赛纪律与访问边界', content: '仅可攻击已开放的比赛端口。禁止访问宿主机管理接口、云元数据地址和其他队伍管理网。', level: 'CRITICAL', published_at: minutesFromNow(-116), status: 'PUBLISHED', pinned: false },
  { id: 'notice-4', title: '赛前检查完成', content: '全部队伍已完成初始化，初始分为 1000 分。', level: 'INFO', published_at: minutesFromNow(-125), status: 'WITHDRAWN', pinned: false },
]

const submissions: Submission[] = [
  { id: 'sub-1', request_id: '01J-DEMO-001', attacker_team_id: 'team-1', attacker_team_name: '白杨', victim_team_id: 'team-3', victim_team_name: '昆仑', service_name: 'Web 服务', result: 'ACCEPTED', attacker_delta: 100, victim_delta: -50, submitted_at: minutesFromNow(-2) },
  { id: 'sub-2', request_id: '01J-DEMO-002', attacker_team_id: 'team-2', attacker_team_name: '胡杨', victim_team_id: 'team-5', victim_team_name: '天山', service_name: 'API 服务', result: 'ACCEPTED', attacker_delta: 100, victim_delta: -50, submitted_at: minutesFromNow(-5) },
  { id: 'sub-3', request_id: '01J-DEMO-003', attacker_team_id: 'team-1', attacker_team_name: '白杨', victim_team_id: 'team-3', victim_team_name: '昆仑', service_name: 'Web 服务', result: 'DUPLICATE', attacker_delta: 0, victim_delta: 0, submitted_at: minutesFromNow(-7) },
  { id: 'sub-4', request_id: '01J-DEMO-004', attacker_team_id: 'team-4', attacker_team_name: '塔河', result: 'INVALID', attacker_delta: 0, victim_delta: 0, submitted_at: minutesFromNow(-9) },
  { id: 'sub-5', request_id: '01J-DEMO-005', attacker_team_id: 'team-3', attacker_team_name: '昆仑', victim_team_id: 'team-3', victim_team_name: '昆仑', service_name: '数据库题服务', result: 'OWN_TEAM', attacker_delta: 0, victim_delta: 0, submitted_at: minutesFromNow(-14) },
]

const ledger: ScoreLedger[] = [
  { id: 'ledger-1', team_id: 'team-1', team_name: '白杨', submission_id: 'sub-1', delta: 100, score_after: teams[0].current_score, reason: '有效攻击', created_at: minutesFromNow(-2) },
  { id: 'ledger-2', team_id: 'team-3', team_name: '昆仑', submission_id: 'sub-1', delta: -50, score_after: teams[2].current_score, reason: '被有效攻击', created_at: minutesFromNow(-2) },
]

const auditLogs: AuditLog[] = [
  { id: 'audit-1', actor_id: 'user-admin', actor_name: 'admin', action: 'TARGET_RESTART', object_type: 'target', object_id: 'target-8-1', detail: '保留原数据卷，执行受控重启', request_id: '01J-ADMIN-018', created_at: minutesFromNow(-8) },
  { id: 'audit-2', actor_id: 'user-admin', actor_name: 'admin', action: 'ANNOUNCEMENT_PUBLISH', object_type: 'announcement', object_id: 'notice-2', detail: '发布服务恢复公告', request_id: '01J-ADMIN-017', created_at: minutesFromNow(-11) },
  { id: 'audit-3', actor_id: 'user-admin', actor_name: 'admin', action: 'MATCH_START', object_type: 'match', object_id: 'match-demo', detail: '开始比赛，启用 300 秒 Flag 轮换', request_id: '01J-ADMIN-002', created_at: minutesFromNow(-118) },
  { id: 'audit-4', actor_id: null, actor_name: 'worker', action: 'FLAG_ROTATE', object_type: 'round', object_id: 'round-24', detail: '30 个靶机完成轮换，0 个写入失败', created_at: minutesFromNow(-3) },
]

let session: User | null = null
const passwords = new Map<string, string>([['admin', 'Admin123!'], ['player1', 'Player123!'], ['player2', 'Player123!'], ['player3', 'Player123!']])
const acceptedDemoFlags = new Set<string>()
const wait = () => new Promise(resolve => setTimeout(resolve, 160))
const requireUser = () => {
  if (!session) throw new Error('请先登录后再继续。')
  return session
}
const requireAdmin = () => {
  const user = requireUser()
  if (user.role !== 'ADMIN') throw new Error('当前账号没有管理员权限。')
  return user
}
const audit = (action: string, objectType: string, objectId: string, detail: string) => {
  const user = requireUser()
  auditLogs.unshift({ id: uid(), actor_id: user.id, actor_name: user.username, action, object_type: objectType, object_id: objectId, detail, request_id: uid(), created_at: now() })
}
const syncMatchTime = () => { match.server_time = now() }

export const demo = {
  async login(payload: LoginPayload) {
    await wait()
    const user = users.find(item => item.username === payload.username && item.status === 'ACTIVE')
    const validPassword = passwords.get(payload.username) === payload.password
    if (!user || !validPassword) throw new Error('用户名或密码不正确，请检查后重试。')
    session = clone(user)
    return clone(user)
  },
  async register(payload: RegisterPayload) {
    await wait()
    const team = teams.find(item => item.invite_code === payload.invite_code.trim().toUpperCase())
    if (!team) throw new Error('邀请码无效，请向管理员确认队伍邀请码。')
    if (team.member_count >= 4) throw new Error('该队伍已有 4 名选手，请选择其他队伍。')
    if (users.some(item => item.username === payload.username)) throw new Error('该用户名已被使用。')
    const user: User = { id: uid(), username: payload.username, role: 'PLAYER', team_id: team.id, team_name: team.name, status: 'ACTIVE' }
    users.push(user)
    passwords.set(user.username, payload.password)
    team.member_count += 1
    session = clone(user)
    return clone(user)
  },
  async logout() { await wait(); session = null; return null },
  async me() { await wait(); return clone(requireUser()) },
  async match() { await wait(); requireUser(); syncMatchTime(); return clone(match) },
  async scoreboard(): Promise<Scoreboard> {
    await wait(); requireUser()
    const rows = teams.map(team => ({
      ...clone(team), rank: 0,
      services: targets.filter(target => target.team_id === team.id).map(target => ({ service_code: target.service_code, service_name: target.service_name, status: target.status })),
    })).sort((a, b) => b.current_score - a.current_score || b.attack_count - a.attack_count || a.unhealthy_seconds - b.unhealthy_seconds || (a.last_scored_at ?? '').localeCompare(b.last_scored_at ?? '') || a.team_no - b.team_no)
    rows.forEach((row, index) => { row.rank = index + 1 })
    return { version: submissions.length + 124, generated_at: now(), frozen: match.score_frozen, rows }
  },
  async targetsMine() {
    await wait(); const user = requireUser()
    return clone(targets.filter(target => target.team_id === user.team_id))
  },
  async submissionsMine() {
    await wait(); const user = requireUser()
    return clone(submissions.filter(item => item.attacker_team_id === user.team_id))
  },
  async announcements(includeAll = false) {
    await wait(); requireUser()
    return clone(announcements.filter(item => includeAll || item.status === 'PUBLISHED'))
  },
  async submitFlag(flag: string): Promise<FlagResult> {
    await wait(); const user = requireUser()
    if (user.role !== 'PLAYER' || !user.team_id) throw new Error('只有已加入队伍的选手可以提交 Flag。')
    const team = teams.find(item => item.id === user.team_id)!
    let result: FlagResult['result'] = 'INVALID'
    let victim: Team | undefined
    let serviceName: string | null = null
    if (match.status !== 'RUNNING') result = 'MATCH_NOT_RUNNING'
    else {
      const matched = /^flag\{t(\d{2})-(web|api|db)-r24\}$/.exec(flag.trim())
      if (flag.trim() === 'flag{expired-demo}') result = 'EXPIRED'
      else if (matched) {
        victim = teams[Number(matched[1]) - 1]
        serviceName = serviceTemplates.find(item => item.code === matched[2])?.name ?? null
        if (!victim) result = 'INVALID'
        else if (victim.id === team.id) result = 'OWN_TEAM'
        else if (acceptedDemoFlags.has(`${team.id}:${flag}`)) result = 'DUPLICATE'
        else {
          result = 'ACCEPTED'
          acceptedDemoFlags.add(`${team.id}:${flag}`)
          team.current_score += 100
          team.attack_count += 1
          team.last_scored_at = now()
          victim.current_score -= 50
          victim.breached_count += 1
        }
      }
    }
    const accepted = result === 'ACCEPTED' && victim
    const submission: Submission = {
      id: uid(), request_id: uid(), user_id: user.id, username: user.username,
      attacker_team_id: team.id, attacker_team_name: team.name,
      victim_team_id: victim?.id, victim_team_name: victim?.name, service_name: serviceName,
      result, attacker_delta: accepted ? 100 : 0, victim_delta: accepted ? -50 : 0, submitted_at: now(),
    }
    submissions.unshift(submission)
    if (accepted && victim) {
      ledger.unshift(
        { id: uid(), team_id: team.id, team_name: team.name, submission_id: submission.id, delta: 100, score_after: team.current_score, reason: '有效攻击', created_at: now() },
        { id: uid(), team_id: victim.id, team_name: victim.name, submission_id: submission.id, delta: -50, score_after: victim.current_score, reason: '被有效攻击', created_at: now() },
      )
    }
    return { result, attacker_delta: accepted ? 100 : 0, victim_delta: accepted ? -50 : 0, attacker_score: team.current_score }
  },
  async restartTarget(id: string) {
    await wait(); const user = requireUser()
    const target = targets.find(item => item.id === id)
    if (!target) throw new Error('未找到该靶机。')
    if (user.role !== 'ADMIN' && target.team_id !== user.team_id) throw new Error('只能操作本队靶机。')
    target.status = 'RUNNING'; target.restart_count += 1; target.last_checked_at = now(); target.error = null
    audit('TARGET_RESTART', 'target', id, '保留原数据卷，执行受控重启')
    return clone(target)
  },
  async changeTargetState(id: string, action: 'start' | 'stop') {
    await wait(); requireAdmin()
    const target = targets.find(item => item.id === id)
    if (!target) throw new Error('未找到该靶机。')
    target.status = action === 'start' ? 'STARTING' : 'STOPPED'
    target.last_checked_at = now()
    audit(`TARGET_${action.toUpperCase()}`, 'target', id, action === 'start' ? '启动靶机容器' : '停止靶机容器')
    return clone(target)
  },
  async healthRecords(id: string) {
    await wait(); requireAdmin()
    const target = targets.find(item => item.id === id)
    if (!target) throw new Error('未找到该靶机。')
    const checks = [1, 2, 3, 4, 5].map(index => ({
      id: `${id}-check-${index}`,
      target_id: id,
      status: index === 1 ? 'UNHEALTHY' : 'HEALTHY',
      duration_ms: index === 1 ? 0 : 40 + index * 7,
      error: index === 1 ? (target.error || '检查超时') : '',
      checked_at: minutesFromNow(-index * 0.5),
    }))
    return checks
  },
  async overview(): Promise<AdminOverview> {
    await wait(); requireAdmin(); syncMatchTime()
    return {
      match: clone(match), team_count: teams.length, online_team_count: teams.filter(item => item.status === 'ACTIVE').length,
      player_count: users.filter(item => item.role === 'PLAYER').length,
      healthy_target_count: targets.filter(item => item.status === 'RUNNING').length, target_count: targets.length,
      abnormal_targets: clone(targets.filter(item => item.status !== 'RUNNING')), latest_submissions: clone(submissions.slice(0, 6)),
    }
  },
  async teams() { await wait(); requireAdmin(); return clone(teams) },
  async createTeam(payload: TeamPayload) {
    await wait(); requireAdmin()
    if (teams.length >= 15) throw new Error('最多可创建 15 支队伍。')
    if (teams.some(item => item.team_no === payload.team_no || item.name === payload.name)) throw new Error('队伍编号和名称必须唯一。')
    const team: Team = { id: uid(), ...payload, invite_code: `TARC-${String(payload.team_no).padStart(2, '0')}-2026`, current_score: 1000, attack_count: 0, breached_count: 0, member_count: 0, status: 'ACTIVE', unhealthy_seconds: 0, last_scored_at: null }
    teams.push(team); audit('TEAM_CREATE', 'team', team.id, `创建队伍 ${team.name}`); return clone(team)
  },
  async updateTeam(id: string, payload: Partial<Team> & { reset_score?: boolean }) {
    await wait(); requireAdmin(); const team = teams.find(item => item.id === id)
    if (!team) throw new Error('未找到该队伍。')
    const resetScore = payload.reset_score
    Object.assign(team, payload)
    delete (team as Team & { reset_score?: boolean }).reset_score
    if (resetScore) { team.current_score = 1000; team.attack_count = 0; team.breached_count = 0 }
    audit('TEAM_UPDATE', 'team', id, resetScore ? '更新队伍并初始化分数' : '更新队伍资料')
    return clone(team)
  },
  async users() { await wait(); requireAdmin(); return clone(users) },
  async createUser(payload: UserPayload) {
    await wait(); requireAdmin()
    if (users.some(item => item.username === payload.username)) throw new Error('该用户名已被使用。')
    const team = teams.find(item => item.id === payload.team_id)
    if (team && team.member_count >= 4) throw new Error('该队伍已有 4 名选手。')
    const user: User = { id: uid(), username: payload.username, role: payload.role, team_id: payload.team_id, team_name: team?.name, status: 'ACTIVE' }
    users.push(user); if (team) team.member_count += 1
    passwords.set(user.username, payload.password || 'Player123!')
    audit('USER_CREATE', 'user', user.id, `创建账号 ${user.username}`); return clone(user)
  },
  async updateUser(id: string, payload: Partial<User> & { password?: string }) {
    await wait(); requireAdmin(); const user = users.find(item => item.id === id)
    if (!user) throw new Error('未找到该选手。')
    if (user.team_id !== payload.team_id && payload.team_id !== undefined) {
      const oldTeam = teams.find(item => item.id === user.team_id)
      const newTeam = teams.find(item => item.id === payload.team_id)
      if (newTeam && newTeam.member_count >= 4) throw new Error('目标队伍已有 4 名选手。')
      if (oldTeam) oldTeam.member_count -= 1
      if (newTeam) newTeam.member_count += 1
    }
    const { password, ...attributes } = payload
    Object.assign(user, attributes)
    if (password) passwords.set(user.username, password)
    user.team_name = teams.find(item => item.id === user.team_id)?.name ?? null
    audit('USER_UPDATE', 'user', id, '更新账号、队伍或状态'); return clone(user)
  },
  async deleteUser(id: string) {
    await wait(); requireAdmin()
    const index = users.findIndex(item => item.id === id)
    if (index < 0) throw new Error('未找到该选手。')
    const user = users[index]
    if (user.role !== 'PLAYER') throw new Error('只能删除选手账号。')
    const team = teams.find(item => item.id === user.team_id)
    if (team) team.member_count = Math.max(0, team.member_count - 1)
    users.splice(index, 1)
    passwords.delete(user.username)
    audit('USER_DELETE', 'user', id, `删除选手 ${user.username}`)
    return null
  },
  async matchAction(action: 'ready' | 'start' | 'pause' | 'resume' | 'finish' | 'freeze') {
    await wait(); requireAdmin()
    if (action === 'ready') match.status = 'READY'
    if (action === 'start') { match.status = 'RUNNING'; match.paused_at = null }
    if (action === 'pause') { match.status = 'PAUSED'; match.paused_at = now() }
    if (action === 'resume') {
      if (match.paused_at) match.ends_at = new Date(new Date(match.ends_at).getTime() + Date.now() - new Date(match.paused_at).getTime()).toISOString()
      match.status = 'RUNNING'; match.paused_at = null
    }
    if (action === 'finish') match.status = 'FINISHED'
    if (action === 'freeze') match.score_frozen = !match.score_frozen
    match.frozen_at = match.score_frozen ? now() : null
    syncMatchTime(); audit(`MATCH_${action.toUpperCase()}`, 'match', match.id, `执行比赛操作 ${action}`)
    return clone(match)
  },
  async createMatch(payload: Pick<Match, 'name' | 'starts_at' | 'ends_at' | 'round_seconds' | 'grace_seconds'>) {
    await wait(); requireAdmin()
    Object.assign(match, payload, { id: uid(), status: 'DRAFT', current_round: 0, score_frozen: false, frozen_at: null, paused_at: null, server_time: now() })
    audit('MATCH_CREATE', 'match', match.id, `创建比赛 ${match.name}`)
    return clone(match)
  },
  async updateMatch(payload: Partial<Match>) {
    await wait(); requireAdmin(); Object.assign(match, payload); syncMatchTime()
    audit('MATCH_CONFIG', 'match', match.id, '更新比赛时间与轮换参数'); return clone(match)
  },
  async targets() { await wait(); requireAdmin(); return clone(targets) },
  async initializeTargets() {
    await wait(); requireAdmin()
    for (const team of teams) {
      for (const [serviceIndex, service] of serviceTemplates.entries()) {
        if (targets.some(item => item.team_id === team.id && item.service_code === service.code)) continue
        targets.push({ id: uid(), team_id: team.id, team_no: team.team_no, team_name: team.name, service_id: `service-${serviceIndex + 1}`, service_code: service.code, service_name: service.name, protocol: service.protocol, attack_ip: `172.31.${team.team_no}.${serviceIndex + 1}`, public_port: 20000 + team.team_no * 100 + serviceIndex + 1, internal_port: service.internal_port, container_name: `target-t${String(team.team_no).padStart(2, '0')}-s0${serviceIndex + 1}`, status: 'RUNNING', last_checked_at: now(), restart_count: 0 })
      }
    }
    audit('TARGET_INITIALIZE', 'match', match.id, '按队伍与服务模板幂等初始化靶机')
    return clone(targets)
  },
  async submissions() { await wait(); requireAdmin(); return clone(submissions) },
  async ledger() { await wait(); requireAdmin(); return clone(ledger) },
  async adjustScore(teamId: string, delta: number, reason: string) {
    await wait(); requireAdmin(); const team = teams.find(item => item.id === teamId)
    if (!team) throw new Error('未找到该队伍。')
    if (!reason.trim()) throw new Error('人工改分必须填写原因。')
    team.current_score += delta
    const entry: ScoreLedger = { id: uid(), team_id: team.id, team_name: team.name, submission_id: null, delta, score_after: team.current_score, reason: `人工改分：${reason}`, created_at: now() }
    ledger.unshift(entry); audit('SCORE_ADJUST', 'team', team.id, `${delta > 0 ? '+' : ''}${delta} 分，${reason}`)
    return clone(entry)
  },
  async createAnnouncement(payload: AnnouncementPayload) {
    await wait(); requireAdmin()
    const notice: Announcement = { id: uid(), ...payload, published_at: now(), status: 'PUBLISHED' }
    announcements.unshift(notice); audit('ANNOUNCEMENT_PUBLISH', 'announcement', notice.id, notice.title); return clone(notice)
  },
  async updateAnnouncement(id: string, payload: Partial<Announcement>) {
    await wait(); requireAdmin(); const notice = announcements.find(item => item.id === id)
    if (!notice) throw new Error('未找到该公告。')
    Object.assign(notice, payload); audit('ANNOUNCEMENT_UPDATE', 'announcement', id, payload.status === 'WITHDRAWN' ? '撤回公告' : '更新公告'); return clone(notice)
  },
  async auditLogs() { await wait(); requireAdmin(); return clone(auditLogs) },
  async services() { await wait(); requireAdmin(); return clone(serviceCatalog) },
  async createService(payload: ServicePayload) {
    await wait(); requireAdmin()
    if (serviceCatalog.some(item => item.code === payload.code || item.service_no === payload.service_no)) throw new Error('服务代码或编号已存在。')
    const service: Service = { id: uid(), ...payload }
    serviceCatalog.push(service)
    audit('SERVICE_CREATE', 'service', service.id, `创建服务模板 ${service.name}`)
    return clone(service)
  },
  async updateService(id: string, payload: Partial<ServicePayload>) {
    await wait(); requireAdmin()
    const service = serviceCatalog.find(item => item.id === id)
    if (!service) throw new Error('未找到该服务模板。')
    Object.assign(service, payload)
    audit('SERVICE_UPDATE', 'service', id, `更新服务模板 ${service.name}`)
    return clone(service)
  },
  async deleteService(id: string) {
    await wait(); requireAdmin()
    if (targets.some(item => item.service_id === id)) throw new Error('该服务已有靶机实例，不能删除。')
    const index = serviceCatalog.findIndex(item => item.id === id)
    if (index < 0) throw new Error('未找到该服务模板。')
    const [service] = serviceCatalog.splice(index, 1)
    audit('SERVICE_DELETE', 'service', id, `删除服务模板 ${service.name}`)
    return null
  },
  async pullServiceImage(id: string) {
    await wait(); requireAdmin()
    const service = serviceCatalog.find(item => item.id === id)
    if (!service) throw new Error('未找到该服务模板。')
    audit('SERVICE_IMAGE_PULL', 'service', id, `预检镜像 ${service.image}`)
    return { image: service.image }
  },
  async exportScores() {
    await wait(); requireAdmin()
    const lines = ['队伍编号,队伍名称,当前总分,有效攻击,被攻击', ...teams.map(team => `${team.team_no},${team.name},${team.current_score},${team.attack_count},${team.breached_count}`)]
    return new Blob([`﻿${lines.join('\n')}`], { type: 'text/csv;charset=utf-8' })
  },
}
