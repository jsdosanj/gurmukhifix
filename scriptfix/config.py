"""Centralised config loading for scriptfix.

A single loader used by every module so that per-script YAML files can share
rules through an ``extends:`` key. Previously each module loaded its config
independently and ``extends`` was silently ignored; here it is resolved by
merging a parent config into its child (lists are concatenated, scalars are
overridden), which is what lets e.g. ``punjabi`` build on ``gurmukhi`` and
``devanagari`` build on ``hindi`` without duplicating every rule.
"""

from __future__ import annotations

import copy
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


def _merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Merge *child* onto *parent*: list rules concatenate, scalars override."""
    merged = copy.deepcopy(parent)
    for key, value in child.items():
        if key == "extends":
            continue
        if (
            key in _LIST_KEYS
            and isinstance(value, list)
            and isinstance(parent.get(key), list)
        ):
            merged[key] = copy.deepcopy(parent[key]) + copy.deepcopy(value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_config(language: str, _seen: tuple[str, ...] = ()) -> dict[str, Any]:
    """Load the config for *language*, resolving any ``extends:`` chain.

    Raises FileNotFoundError for an unknown language and ValueError on a
    circular ``extends`` reference.
    """
    if language in _seen:
        chain = " -> ".join((*_seen, language))
        raise ValueError(f"Circular 'extends' in config chain: {chain}")

    cfg = _read_raw(language)
    parent_name = cfg.get("extends")
    if parent_name:
        parent = load_config(parent_name, _seen + (language,))
        cfg = _merge(parent, cfg)
    return cfg
