"""Check the environment against the rules in docs/ENV.md.

Reports only. It never rewrites config or atuin vars (docs/ENV-HANDOVER.md).
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from skogai.env.areas import AREAS
from skogai.env.inventory import SECRET_NAME, is_dir_var


@dataclass(frozen=True)
class Finding:
    level: str  # "error" or "warning"
    rule: str  # "naming", "overlap", "secret" or "unverified"
    message: str


def _normalise(path: str) -> str:
    return os.path.normpath(os.path.expanduser(path))


def _concept(name: str) -> str:
    """Strip XDG_, SKOGAI and _DIR, so names for one concept group together."""
    tokens = name.split("_")
    if tokens[:1] == ["XDG"]:
        tokens = tokens[1:]
    tokens = [t for t in tokens if t not in ("SKOGAI", "DIR")]
    return "_".join(tokens)


def check(
    env: Mapping[str, str],
    atuin_names: Sequence[str] | None,
) -> list[Finding]:
    findings: list[Finding] = []

    # Naming rules.
    for name, value in sorted(env.items()):
        if name.startswith("XDG_SKOGAI_"):
            findings.append(Finding(
                "error", "naming",
                f"{name}: XDG_SKOGAI_* names are not allowed, use SKOGAI_*",
            ))
        if is_dir_var(name):
            parts = name.split("_")
            area = parts[1] if parts[0] == "SKOGAI" else None
            # SKOGAI_DIR is the root, it has no area segment.
            if area and area != "DIR" and area not in AREAS:
                findings.append(Finding(
                    "warning", "naming",
                    f"{name}: area '{area}' is not in the fixed list",
                ))
            if not os.path.isabs(value) or not value.endswith("/"):
                findings.append(Finding(
                    "warning", "naming",
                    f"{name}: directory values should be absolute and end in '/'",
                ))

    # Overlap: several names for one concept.
    groups: dict[str, list[str]] = defaultdict(list)
    for name in env:
        if is_dir_var(name):
            groups[_concept(name)].append(name)
    for concept, names in sorted(groups.items()):
        if len(names) < 2:
            continue
        names.sort()
        paths = {_normalise(env[n]) for n in names}
        listing = ", ".join(names)
        if len(paths) > 1:
            findings.append(Finding(
                "error", "overlap",
                f"{listing} point at different paths",
            ))
        else:
            findings.append(Finding(
                "warning", "overlap",
                f"{listing} are several names for one concept",
            ))

    # Secrets in the atuin list. Names only, values are never printed.
    if atuin_names is None:
        findings.append(Finding(
            "warning", "unverified",
            "could not read the atuin var list, secret check skipped",
        ))
    else:
        for name in atuin_names:
            if SECRET_NAME.search(name):
                findings.append(Finding(
                    "error", "secret",
                    f"{name}: secret-looking name in the atuin var list (value not shown)",
                ))

    return findings
