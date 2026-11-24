"""Routine maintenance tasks (run from backend\\ with the project's Python).

    ..\\.venv\\Scripts\\python.exe -m app.maintenance purge-sessions --older-than-days 30
    ..\\.venv\\Scripts\\python.exe -m app.maintenance purge-audio --older-than-days 30
    ..\\.venv\\Scripts\\python.exe -m app.maintenance status

- purge-sessions: deletes login sessions that expired or were revoked more than
  N days ago (they are useless and only grow the table).
- purge-audio: only relevant when AUDIO_KEEP_AFTER_PROCESSING=true; deletes kept
  recordings older than N days and records the deletion time.
Nothing here touches patients, intakes, consent or audit records.
"""

import argparse
import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, or_, select

from app.core.clock import now_utc
from app.database.models import AudioTranscription, AuthSession
from app.database.session import SessionLocal


def purge_sessions(db, older_than_days: int) -> int:
    cutoff = now_utc() - timedelta(days=older_than_days)
    result = db.execute(delete(AuthSession).where(or_(
        AuthSession.expires_at < cutoff,
        AuthSession.revoked_at < cutoff)))
    db.commit()
    return result.rowcount or 0


def purge_audio(db, older_than_days: int) -> int:
    cutoff = now_utc() - timedelta(days=older_than_days)
    rows = db.scalars(select(AudioTranscription).where(
        AudioTranscription.audio_path.is_not(None), AudioTranscription.created_at < cutoff)).all()
    for r in rows:
        try:
            Path(r.audio_path).unlink(missing_ok=True)
        except OSError:
            continue
        r.audio_path = None
        r.audio_deleted_at = now_utc()
    db.commit()
    return len(rows)


def status(db) -> dict:
    now = now_utc()
    return {
        "active_sessions": db.scalar(select(func.count()).select_from(AuthSession).where(
            AuthSession.revoked_at.is_(None), AuthSession.expires_at > now)),
        "stored_sessions": db.scalar(select(func.count()).select_from(AuthSession)),
        "kept_audio_files": db.scalar(select(func.count()).select_from(AudioTranscription).where(
            AudioTranscription.audio_path.is_not(None))),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("purge-sessions", "purge-audio"):
        p = sub.add_parser(name)
        p.add_argument("--older-than-days", type=int, default=30)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    with SessionLocal() as db:
        if args.cmd == "purge-sessions":
            print(f"Deleted {purge_sessions(db, args.older_than_days)} old sessions.")
        elif args.cmd == "purge-audio":
            print(f"Deleted {purge_audio(db, args.older_than_days)} kept audio files.")
        else:
            for k, v in status(db).items():
                print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
