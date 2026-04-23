from __future__ import annotations

import re



def _normalize(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', name.lower().strip())



def guess_default_mapping(columns: list[str], import_type: str) -> dict[str, str | None]:
    lookup = {_normalize(col): col for col in columns}

    def find(*names: str) -> str | None:
        for name in names:
            normalized = _normalize(name)
            if normalized in lookup:
                return lookup[normalized]
        return None

    if import_type == "Sales":
        return {
            "project_id": find("project_id", "project id", "projectid"),
            "project_name": find("project_name", "project name", "project name (current)", "project"),
            "client_code": find("client_code", "client code", "client", "code"),
        }

    return {
        "project_id": find("project_id", "project id", "projectid"),
        "client_code": find("client_code", "client code", "client", "code"),
        "order_no": find("order_no", "order no", "order no.", "order number", "order"),
    }
