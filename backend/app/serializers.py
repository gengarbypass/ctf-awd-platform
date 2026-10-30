from .models import Announcement, Match, Service, Submission, Target, Team, User, as_utc, utcnow


def iso(value):
    return as_utc(value).isoformat() if value else None


def user_dict(user: User) -> dict:
    team = user.__dict__.get("team")
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role.value,
        "team_id": user.team_id,
        "team_name": team.name if team else None,
        "status": user.status.value,
        "last_login_at": iso(user.last_login_at),
        "team": team_dict(team) if team else None,
    }


def team_dict(team: Team, unhealthy_seconds: int = 0) -> dict:
    users = team.__dict__.get("users")
    return {
        "id": team.id,
        "team_no": team.team_no,
        "name": team.name,
        "invite_code": team.invite_code,
        "current_score": team.current_score,
        "attack_count": team.attack_count,
        "breached_count": team.breached_count,
        "member_count": len(users or []),
        "status": team.status.value,
        "unhealthy_seconds": unhealthy_seconds,
        "last_scored_at": iso(team.last_score_at),
        "last_score_at": iso(team.last_score_at),
    }


def match_dict(match: Match) -> dict:
    now = utcnow()
    reference = as_utc(match.paused_at) if match.status.value == "PAUSED" and match.paused_at else now
    remaining = max(0, int((as_utc(match.ends_at) - reference).total_seconds())) if match.status.value in {"RUNNING", "PAUSED"} else None
    return {
        "id": match.id,
        "name": match.name,
        "status": match.status.value,
        "starts_at": iso(match.starts_at),
        "ends_at": iso(match.ends_at),
        "server_time": iso(now),
        "paused_at": iso(match.paused_at),
        "round_seconds": match.round_seconds,
        "grace_seconds": match.grace_seconds,
        "current_round": match.current_round,
        "score_frozen": match.score_frozen,
        "frozen_at": iso(match.frozen_at),
        "remaining_seconds": remaining,
    }


def service_dict(service: Service) -> dict:
    return {
        "id": service.id,
        "code": service.code,
        "name": service.name,
        "service_no": service.service_no,
        "protocol": service.protocol,
        "internal_port": service.internal_port,
        "public_base_port": service.public_base_port,
        "flag_path": service.flag_path,
        "image": service.image,
        "check_config": service.check_config,
    }


def target_dict(target: Target, include_management: bool = False) -> dict:
    service = target.__dict__.get("service")
    team = target.__dict__.get("team")
    data = {
        "id": target.id,
        "team_id": target.team_id,
        "team_no": team.team_no if team else None,
        "team_name": team.name if team else None,
        "service_id": target.service_id,
        "service_code": service.code if service else None,
        "service_name": service.name if service else None,
        "protocol": service.protocol if service else None,
        "internal_port": service.internal_port if service else None,
        "attack_ip": target.attack_ip,
        "public_port": target.public_port,
        "container_name": target.container_name,
        "status": target.status.value,
        "consecutive_failures": target.consecutive_failures,
        "restart_count": len(target.restart_history or []),
        "last_checked_at": iso(target.last_health_at),
        "last_health_at": iso(target.last_health_at),
        "error": None,
    }
    if include_management:
        data.update(volume_name=target.volume_name, gateway_host=target.gateway_host)
    return data


def submission_dict(item: Submission) -> dict:
    attacker = item.__dict__.get("attacker_team")
    victim = item.__dict__.get("victim_team")
    user = item.__dict__.get("user")
    flag = item.__dict__.get("flag")
    target = flag.__dict__.get("target") if flag else None
    service = target.__dict__.get("service") if target else None
    return {
        "id": item.id,
        "request_id": item.request_id,
        "user_id": item.user_id,
        "username": user.username if user else None,
        "attacker_team_id": item.attacker_team_id,
        "attacker_team_name": attacker.name if attacker else None,
        "victim_team_id": item.victim_team_id,
        "victim_team_name": victim.name if victim else None,
        "flag_id": item.flag_id,
        "service_name": service.name if service else None,
        "result": item.result.value,
        "attacker_delta": item.attacker_delta,
        "victim_delta": item.victim_delta,
        "submitted_at": iso(item.submitted_at),
    }


def announcement_dict(item: Announcement) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "level": item.level,
        "status": item.status.value,
        "pinned": item.is_pinned,
        "is_pinned": item.is_pinned,
        "published_at": iso(item.published_at),
    }
