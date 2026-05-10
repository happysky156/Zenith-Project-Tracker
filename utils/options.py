from __future__ import annotations

from typing import Iterable, Sequence, TypeVar

T = TypeVar("T")


def _sort_key(value: object) -> str:
    return str(value or "").strip().casefold()


def sorted_dropdown_options(options: Iterable[T], pinned: Sequence[T] = ("", "All")) -> list[T]:
    """Return dropdown options sorted alphabetically, while keeping blank/All-style values first.

    This is for user-facing Streamlit selectbox/multiselect options. It keeps the
    original value objects intact, removes duplicate string-equivalent values, and
    sorts the remaining choices case-insensitively for easier lookup.
    """
    option_list = list(options or [])
    result: list[T] = []
    seen: set[str] = set()

    def add(value: T) -> None:
        key = str(value or "").strip().casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)

    for pin in pinned:
        for option in option_list:
            if str(option or "").strip().casefold() == str(pin or "").strip().casefold():
                add(option)
                break

    remaining = [
        option for option in option_list
        if str(option or "").strip().casefold() not in seen
    ]
    for option in sorted(remaining, key=_sort_key):
        add(option)
    return result
