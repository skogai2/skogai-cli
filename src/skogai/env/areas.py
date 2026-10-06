"""The fixed list of areas, and how each one falls back to a directory.

The list is changed deliberately, not per tool (docs/ENV.md, Naming).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Area:
    name: str
    # XDG base variable for this area, if it has one.
    xdg_var: str | None
    # Hardcoded default, relative to $HOME, used when nothing else is set.
    home_default: str
    # Whether the path goes under a skogai/ directory below the base.
    skogai_subdir: bool


AREAS: dict[str, Area] = {
    area.name: area
    for area in (
        Area("CONFIG", "XDG_CONFIG_HOME", ".config", skogai_subdir=True),
        Area("DATA", "XDG_DATA_HOME", ".local/share", skogai_subdir=True),
        Area("STATE", "XDG_STATE_HOME", ".local/state", skogai_subdir=True),
        Area("CACHE", "XDG_CACHE_HOME", ".cache", skogai_subdir=True),
        Area("CLAUDE", None, "claude", skogai_subdir=False),
    )
}

# The skogai home. Open question 1 in docs/ENV-HANDOVER.md: the canonical
# name is not agreed yet. SKOGAI_DIR is the leaning there, not a decision.
ROOT_VARS: tuple[str, ...] = ("SKOGAI_DIR",)
ROOT_DEFAULT = "skogai"
