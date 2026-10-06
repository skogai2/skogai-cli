"""Read the environment, and the names in the atuin dotfiles var list.

Values from the atuin list are never read or printed, only names: that
list is where secrets must not end up, so the check works on names alone.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping

XDG_BASE_VARS = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME")

SECRET_NAME = re.compile(r"_(TOKEN|KEY|PASSWORD|SECRET)$")
_EXPORT_LINE = re.compile(r"^export ([A-Za-z_][A-Za-z0-9_]*)=")


def is_dir_var(name: str) -> bool:
    """A skogai directory variable: SKOGAI_*_DIR or XDG_SKOGAI_*_DIR."""
    return name.endswith("_DIR") and name.startswith(("SKOGAI_", "XDG_SKOGAI_"))


def relevant(env: Mapping[str, str]) -> dict[str, str]:
    """The variables that matter to skogai: skogai names and XDG base dirs."""
    return {
        k: v
        for k, v in env.items()
        if k.startswith(("SKOGAI_", "XDG_SKOGAI_")) or k in XDG_BASE_VARS
    }


def parse_atuin_var_list(text: str) -> list[str]:
    """Names from `atuin dotfiles var list` output. Values are dropped."""
    names = []
    for line in text.splitlines():
        m = _EXPORT_LINE.match(line)
        if m:
            names.append(m.group(1))
    return names


def atuin_var_names() -> list[str] | None:
    """Names in the atuin dotfiles var list, or None if it cannot be read."""
    try:
        proc = subprocess.run(
            ["atuin", "dotfiles", "var", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return parse_atuin_var_list(proc.stdout)
