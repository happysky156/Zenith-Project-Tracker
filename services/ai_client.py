from __future__ import annotations

import json
from typing import Any

import streamlit as st
from openai import OpenAI


class AIConfigError(RuntimeError):
    """Raised when the AI API settings are missing or invalid."""


class AIResponseError(RuntimeError):
    """Raised when the AI API returns a response that cannot be used."""


def _read_ai_secret(name: str, default: Any = None) -> Any:
    """Read AI settings from Streamlit secrets.

    Expected format in .streamlit/secrets.toml or Streamlit Cloud Secrets:

    [AI]
    DEEPSEEK_API_KEY = "..."
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    DEEPSEEK_MODEL = "deepseek-chat"
    """
    try:
        ai_settings = st.secrets.get("AI", {})
        if name in ai_settings:
            return ai_settings.get(name, default)
    except Exception:
        pass

    # Optional fallback: allow flat secrets if the app owner prefers it later.
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def get_ai_settings() -> dict[str, Any]:
    api_key = _read_ai_secret("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise AIConfigError(
            "Missing AI.DEEPSEEK_API_KEY. Please add it to Streamlit Secrets first."
        )

    return {
        "api_key": str(api_key),
        "base_url": str(_read_ai_secret("DEEPSEEK_BASE_URL", "https://api.deepseek.com")),
        "model": str(_read_ai_secret("DEEPSEEK_MODEL", "deepseek-chat")),
        "timeout": int(_read_ai_secret("AI_TIMEOUT_SECONDS", 45)),
        "max_tokens": int(_read_ai_secret("AI_MAX_TOKENS", 2500)),
    }


def get_deepseek_client() -> tuple[OpenAI, dict[str, Any]]:
    settings = get_ai_settings()
    client = OpenAI(
        api_key=settings["api_key"],
        base_url=settings["base_url"],
        timeout=settings["timeout"],
    )
    return client, settings


def call_deepseek_json(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
) -> dict[str, Any]:
    """Call DeepSeek and ask for a strict JSON object response."""
    client, settings = get_deepseek_client()

    response = client.chat.completions.create(
        model=settings["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=settings["max_tokens"],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        # Some compatible APIs may still return a JSON-looking object with leading/trailing
        # text or markdown fences. Try one conservative extraction before falling back.
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`").strip()
            if stripped.lower().startswith("json"):
                stripped = stripped[4:].strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            candidate = stripped[start : end + 1]
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                raise AIResponseError(f"AI returned invalid JSON: {content[:1200]}") from exc
        else:
            raise AIResponseError(f"AI returned invalid JSON: {content[:1200]}") from exc

    if not isinstance(parsed, dict):
        raise AIResponseError("AI response must be a JSON object.")

    return parsed
