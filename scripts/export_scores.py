#!/usr/bin/env python3
import asyncio
import csv
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select

from app.database import SessionLocal, dispose_database
from app.models import ScoreLedger, Team
from app.serializers import iso


async def export(destination: str) -> None:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with SessionLocal() as db:
        teams = list((await db.execute(select(Team).order_by(Team.team_no))).scalars())
        team_map = {team.id: team for team in teams}
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(["record_type", "team_no", "team_name", "team_id", "score_or_delta", "score_after", "attack_count", "breached_count", "reason", "submission_id", "created_at"])
            for team in teams:
                writer.writerow(["TEAM", team.team_no, team.name, team.id, team.current_score, team.current_score, team.attack_count, team.breached_count, "", "", ""])
            ledgers = (await db.execute(select(ScoreLedger).order_by(ScoreLedger.created_at))).scalars().all()
            for item in ledgers:
                team = team_map[item.team_id]
                writer.writerow(["LEDGER", team.team_no, team.name, team.id, item.delta, item.score_after, "", "", item.reason.value, item.submission_id or "", iso(item.created_at)])
    await dispose_database()
    print(path.resolve())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/export_scores.py OUTPUT.csv")
    asyncio.run(export(sys.argv[1]))
