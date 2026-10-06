"""Resolve an area to a directory, most specific source first.

1. Explicit argument: not implemented yet (add when a script needs it).
2. App-specific variable: SKOGAI_<AREA>[_<COMPONENT>...]_DIR
3. XDG base directory, under skogai/ for areas that use it.
4. Hardcoded default under $HOME.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from skogai.env.areas import AREAS, ROOT_DEFAULT, ROOT_VARS


@dataclass(frozen=True)
class Resolution:
    path: str  # normalised: no trailing slash, expanded ~
    tier: str  # "app", "xdg" or "default"
    var: str | None  # the variable that supplied the value, if any


def var_name(area: str, components: Sequence[str] = ()) -> str:
    """The app-specific variable name for an area and its components."""
    parts = [area, *(c.upper().replace("-", "_") for c in components)]
    return "SKOGAI_" + "_".join(parts) + "_DIR"


def _clean(path: str) -> str:
    return os.path.normpath(os.path.expanduser(path))


def resolve(
    area: str | None = None,
    components: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
) -> Resolution:
    """Resolve a path. With no area, resolves the skogai home itself.

    The caller validates the area name and components.
    """
    env = os.environ if env is None else env
    home = env.get("HOME") or os.path.expanduser("~")

    if area is None:
        for var in ROOT_VARS:
            if env.get(var):
                return Resolution(_clean(env[var]), "app", var)
        return Resolution(_clean(os.path.join(home, ROOT_DEFAULT)), "default", None)

    spec = AREAS[area]

    name = var_name(area, components)
    if env.get(name):
        return Resolution(_clean(env[name]), "app", name)

    rel = ["skogai"] if spec.skogai_subdir else []
    rel.extend(components)

    if spec.xdg_var and env.get(spec.xdg_var):
        base, tier, var = env[spec.xdg_var], "xdg", spec.xdg_var
    else:
        base, tier, var = os.path.join(home, spec.home_default), "default", None

    return Resolution(_clean(os.path.join(base, *rel)), tier, var)
