"""
Runtime config overrides — a small DB-backed layer over the env-baked Settings.

Motivation: llm_provider / osint_source / osint_rss_enabled are read from env at boot
(config.get_settings() is lru_cache'd, so immutable at runtime). The admin Settings
panel needs to flip these live. Overrides live in the app_config table and are exposed
through a sync, process-local cache so hot paths (llm.active_provider, the on-demand
analyst chat) can read them without a DB round-trip.

Propagation model:
  - The API process refreshes its cache on every admin write (and via load()), so the
    on-demand analyst honours a flip immediately.
  - Worker processes call `await load(db)` at the start of each run, so batch workers
    pick up a flip on their next cycle.
  - With no override row present, effective values equal the env default — so behaviour
    is identical to before this layer existed until an admin sets something.

Safety: paid_apis_enabled is deliberately NOT overridable here. It stays the env-only
master kill-switch for paid Voyage embeddings. The LLM provider is local-only
(ollama/off), so no runtime flip can ever start LLM spend.
"""

import logging

from sqlalchemy import select

from backend.config import get_settings
from backend.models.app_config import AppConfig

logger = logging.getLogger(__name__)

# key -> spec. "choices" = allowed string values; type "bool" = a boolean toggle.
OVERRIDABLE_KEYS: dict[str, dict] = {
    "llm_provider": {"choices": {"ollama", "off"}},
    "osint_source": {"choices": {"gdelt", "reddit"}},
    "osint_rss_enabled": {"type": "bool"},
}

# Process-local cache of currently-set overrides. Empty ⇒ everything on env defaults.
_CACHE: dict[str, object] = {}


# ── validation ────────────────────────────────────────────────────────────────
def validate(key: str, value: object) -> object:
    """Return the coerced value for a set, or raise ValueError. Rejects unknown keys."""
    if key not in OVERRIDABLE_KEYS:
        raise ValueError(f"'{key}' is not an overridable setting")
    spec = OVERRIDABLE_KEYS[key]
    if spec.get("type") == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ValueError(f"'{key}' must be a boolean")
    choices = spec["choices"]
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"'{key}' must be one of {sorted(choices)}")
    return value


# ── cache-backed readers (sync, no DB) ──────────────────────────────────────────
def effective(key: str, default):
    """Overridden value if set this process, else the provided env default."""
    return _CACHE.get(key, default)


def llm_provider() -> str:
    return _CACHE.get("llm_provider") or get_settings().llm_provider


def osint_source() -> str:
    return _CACHE.get("osint_source") or get_settings().osint_source


def osint_rss_enabled() -> bool:
    v = _CACHE.get("osint_rss_enabled")
    return get_settings().osint_rss_enabled if v is None else bool(v)


def snapshot() -> dict:
    """Effective config for every overridable key + whether it's overridden — the
    payload the admin Settings panel renders. Read-only; safe to expose to admins."""
    s = get_settings()
    out: dict[str, dict] = {}
    for key, spec in OVERRIDABLE_KEYS.items():
        env_default = getattr(s, key)
        out[key] = {
            "value": _CACHE.get(key, env_default),
            "default": env_default,
            "overridden": key in _CACHE,
            "choices": sorted(spec["choices"]) if "choices" in spec else None,
            "type": "bool" if spec.get("type") == "bool" else "choice",
        }
    return out


# ── DB access ────────────────────────────────────────────────────────────────
async def load(db) -> dict:
    """Refresh the process cache from the app_config table. Called on API writes and
    at the start of each worker run. Best-effort at the call site — see the worker."""
    rows = (await db.execute(select(AppConfig))).scalars().all()
    _CACHE.clear()
    for r in rows:
        _CACHE[r.key] = r.value
    return dict(_CACHE)


async def upsert(db, key: str, value: object, updated_by: str | None) -> object:
    """Validate + stage an override write (caller commits). Returns the coerced value.
    Passing value=None DELETES the override, reverting the key to its env default."""
    if key not in OVERRIDABLE_KEYS:
        raise ValueError(f"'{key}' is not an overridable setting")
    row = await db.get(AppConfig, key)
    if value is None:
        if row is not None:
            await db.delete(row)
        return None
    coerced = validate(key, value)
    if row is None:
        db.add(AppConfig(key=key, value=coerced, updated_by=updated_by))
    else:
        row.value = coerced
        row.updated_by = updated_by
    await db.flush()
    return coerced
