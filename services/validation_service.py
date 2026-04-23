from __future__ import annotations


def require_required_columns(mapping: dict[str, str | None], required_fields: list[str]) -> bool:
    return all(bool(mapping.get(field)) for field in required_fields)
