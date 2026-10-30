import type { AnnouncementLevel, MatchStatus, SubmissionResult, TargetStatus } from '@/api/types'

export const matchStatus: Record<MatchStatus, { label: string; tone: string }> = {
  DRAFT: { label: '草稿', tone: 'neutral' },
  READY: { label: '待开始', tone: 'info' },
  RUNNING: { label: '进行中', tone: 'success' },
  PAUSED: { label: '已暂停', tone: 'warning' },
  FINISHED: { label: '已结束', tone: 'neutral' },
}

export const targetStatus: Record<TargetStatus, { label: string; tone: string }> = {
  CREATED: { label: '已创建', tone: 'neutral' },
  STARTING: { label: '启动中', tone: 'info' },
  RUNNING: { label: '运行正常', tone: 'success' },
  UNHEALTHY: { label: '服务异常', tone: 'danger' },
  RESTARTING: { label: '恢复中', tone: 'warning' },
  MANUAL_INTERVENTION: { label: '待人工处理', tone: 'danger' },
  STOPPED: { label: '已停止', tone: 'neutral' },
}

export const submissionResult: Record<SubmissionResult, { label: string; tone: string }> = {
  ACCEPTED: { label: '有效攻击', tone: 'success' },
  DUPLICATE: { label: '重复提交', tone: 'warning' },
  OWN_TEAM: { label: '本队 Flag', tone: 'neutral' },
  EXPIRED: { label: '已过期', tone: 'warning' },
  INVALID: { label: '无效 Flag', tone: 'danger' },
  MATCH_NOT_RUNNING: { label: '比赛未进行', tone: 'neutral' },
}

export const announcementLevel: Record<AnnouncementLevel, { label: string; tone: string }> = {
  INFO: { label: '通知', tone: 'info' },
  WARNING: { label: '注意', tone: 'warning' },
  CRITICAL: { label: '重要', tone: 'danger' },
}

export function formatDate(value?: string | null, withSeconds = false) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '暂无'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
    second: withSeconds ? '2-digit' : undefined, hour12: false,
  }).format(date).replaceAll('/', '-')
}

export function formatFullDate(value?: string | null) {
  if (!value) return '暂无'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(value)).replaceAll('/', '-')
}

export function formatDuration(totalSeconds: number) {
  const safe = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const seconds = safe % 60
  return [hours, minutes, seconds].map(value => String(value).padStart(2, '0')).join(':')
}

export function signed(value: number) {
  return value > 0 ? `+${value}` : String(value)
}
