export type Role = 'PLAYER' | 'ADMIN'
export type MatchStatus = 'DRAFT' | 'READY' | 'RUNNING' | 'PAUSED' | 'FINISHED'
export type TargetStatus = 'CREATED' | 'STARTING' | 'RUNNING' | 'UNHEALTHY' | 'RESTARTING' | 'MANUAL_INTERVENTION' | 'STOPPED'
export type SubmissionResult = 'ACCEPTED' | 'DUPLICATE' | 'OWN_TEAM' | 'EXPIRED' | 'INVALID' | 'MATCH_NOT_RUNNING'
export type AnnouncementLevel = 'INFO' | 'WARNING' | 'CRITICAL'

export interface ApiResponse<T> {
  code: string
  message: string
  data: T
  request_id: string
}

export interface Team {
  id: string
  team_no: number
  name: string
  invite_code: string
  current_score: number
  attack_count: number
  breached_count: number
  member_count: number
  status: 'ACTIVE' | 'DISABLED'
  unhealthy_seconds: number
  last_scored_at: string | null
}

export interface User {
  id: string
  username: string
  role: Role
  team_id: string | null
  team_name?: string | null
  status: 'ACTIVE' | 'DISABLED'
  last_login_at?: string | null
}

export interface Match {
  id: string
  name: string
  status: MatchStatus
  starts_at: string
  ends_at: string
  server_time: string
  round_seconds: number
  grace_seconds: number
  current_round: number
  score_frozen: boolean
  frozen_at?: string | null
  paused_at?: string | null
}

export interface ServiceHealth {
  service_code: string
  service_name: string
  status: TargetStatus
}

export interface ScoreboardRow extends Team {
  rank: number
  services: ServiceHealth[]
}

export interface Scoreboard {
  version: number
  generated_at: string
  frozen: boolean
  rows: ScoreboardRow[]
}

export interface Target {
  id: string
  team_id: string
  team_no?: number
  team_name?: string
  service_id: string
  service_code: string
  service_name: string
  protocol: string
  attack_ip: string
  public_port: number
  internal_port: number
  container_name: string
  status: TargetStatus
  last_checked_at: string | null
  restart_count: number
  error?: string | null
}

export interface Submission {
  id: string
  request_id: string
  user_id?: string
  username?: string
  attacker_team_id: string
  attacker_team_name: string
  victim_team_id?: string | null
  victim_team_name?: string | null
  service_name?: string | null
  result: SubmissionResult
  attacker_delta: number
  victim_delta: number
  submitted_at: string
}

export interface FlagResult {
  result: SubmissionResult
  attacker_delta: number
  victim_delta: number
  attacker_score: number
  message?: string
}

export interface Announcement {
  id: string
  title: string
  content: string
  level: AnnouncementLevel
  published_at: string
  status: 'PUBLISHED' | 'WITHDRAWN'
  pinned: boolean
}

export interface AuditLog {
  id: string
  actor_id: string | null
  actor_name: string
  action: string
  object_type: string
  object_id: string
  detail: string
  request_id?: string
  created_at: string
}

export interface ScoreLedger {
  id: string
  team_id: string
  team_name: string
  submission_id: string | null
  delta: number
  score_after: number
  reason: string
  created_at: string
}

export interface HealthCheck {
  id: string
  target_id: string
  status: string
  duration_ms: number
  error: string
  checked_at: string
}

export interface AdminOverview {
  match: Match
  team_count: number
  online_team_count: number
  player_count: number
  healthy_target_count: number
  target_count: number
  abnormal_targets: Target[]
  latest_submissions: Submission[]
}

export interface LoginPayload { username: string; password: string }
export interface RegisterPayload extends LoginPayload { invite_code: string }
export interface TeamPayload { team_no: number; name: string; member_count?: number }
export interface UserPayload { username: string; password?: string; role: Role; team_id: string | null }
export interface AnnouncementPayload { title: string; content: string; level: AnnouncementLevel; pinned: boolean }
