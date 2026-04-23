from __future__ import annotations

import uuid


def new_batch_id() -> str:
    return f"BATCH-{uuid.uuid4().hex[:10].upper()}"


def new_event_id() -> str:
    return f"EVT-{uuid.uuid4().hex[:12].upper()}"


def new_snapshot_id() -> str:
    return f"SNAP-{uuid.uuid4().hex[:12].upper()}"
