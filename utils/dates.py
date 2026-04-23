from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_meeting_week() -> str:
    now = datetime.now(timezone.utc)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def days_since_text(iso_text: str | None) -> str:
    if not iso_text:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_text)
        delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
        return str(delta.days)
    except Exception:
        return "-"
