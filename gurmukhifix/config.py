"""Centralised config loading for gurmukhifix.

A single loader used by every module so that per-script YAML files can share
rules through an ``extends:`` key. Previously each module loaded its config
independently and ``extends`` was silently ignored; here it is resolved by
merging a parent config into its child (lists are concatenated, scalars are
overridden), which is what lets e.g. ``punjabi`` build on ``gurmukhi`` and
``devanagari`` build on ``hindi`` without duplicating every rule.
"""

from __future__ import annotations

import copy
import functools
import json
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).parent / "configs"

# Keys whose values are lists of rules: a child config *adds to* its parent's
# rules rather than replacing them.
_LIST_KEYS = (
    "confusion_pairs",
    "diacritic_pairs",
    "impossible_sequences",
    "valid_ranges",
    "ligature_rules",
)


def _read_raw(language: str) -> dict[str, Any]:
    path = _CONFIG_DIR / f"{language}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No config found for language '{language}' at {path}")
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# How to identify a rule for dedup purposes — by the fields that define its
# *behaviour*, so two entries that only differ in an annotation like ``note`` are
# still recognised as the same correction candidate.
_IDENTITY = {
    "confusion_pairs": lambda r: ("wc", r.get("wrong"), r.get("correct")),
    "diacritic_pairs": lambda r: ("wc", r.get("wrong"), r.get("correct")),
    "ligature_rules": lambda r: ("bj", r.get("broken"), r.get("joined")),
    "impossible_sequences": lambda r: ("p", r.get("pattern")),
}


def _dedup(key: str, items: list[Any]) -> list[Any]:
    """Drop duplicate rules, preserving first occurrence.

    A child config that ``extends`` a parent should not re-list the parent's rules
    (e.g. ``punjabi`` re-listing every ``gurmukhi`` confusion pair): concatenating
    then produces duplicate correction *candidates*, wasting work and skewing any
    frequency-based tie-break. Deduping by behavioural identity makes ``extends``
    idempotent no matter what a config author lists.
    """
    identity = _IDENTITY.get(key)
    seen: set[Any] = set()
    out: list[Any] = []
    for item in items:
        if identity is not None and isinstance(item, dict):
            marker: Any = identity(item)
        else:
            marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out


def _merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Merge *child* onto *parent*: list rules concatenate (deduped), scalars override."""
    merged = copy.deepcopy(parent)
    for key, value in child.items():
        if key == "extends":
            continue
        if (
            key in _LIST_KEYS
            and isinstance(value, list)
            and isinstance(parent.get(key), list)
        ):
            merged[key] = _dedup(key, copy.deepcopy(parent[key]) + copy.deepcopy(value))
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _resolve(language: str, _seen: tuple[str, ...] = ()) -> dict[str, Any]:
    if language in _seen:
        chain = " -> ".join((*_seen, language))
        raise ValueError(f"Circular 'extends' in config chain: {chain}")

    cfg = _read_raw(language)
    parent_name = cfg.get("extends")
    if parent_name:
        parent = _resolve(parent_name, _seen + (language,))
        cfg = _merge(parent, cfg)
    return cfg


@functools.lru_cache(maxsize=None)
def _load_resolved(language: str) -> dict[str, Any]:
    """Parse + merge the config once per language (cached)."""
    return _resolve(language)


def load_config(language: str) -> dict[str, Any]:
    """Load the config for *language*, resolving any ``extends:`` chain.

    The parse-and-merge result is cached per language; a fresh deep copy is
    returned each call so callers may treat it as their own mutable dict.

    Raises FileNotFoundError for an unknown language and ValueError on a
    circular ``extends`` reference.
    """
    return copy.deepcopy(_load_resolved(language))
