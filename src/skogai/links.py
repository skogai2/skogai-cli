"""Link repo config into install paths, as listed in a manifest (links.txt).

Each manifest line is `<repo path, relative to the manifest> <install path>`.
A real file or directory at an install path is never overwritten: move it
into the repo first, then run again.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

MODES = ("link", "check")


@dataclass(frozen=True)
class Entry:
    name: str  # path inside the repo
    target: str  # install path, may start with ~


def parse_manifest(text: str) -> list[Entry]:
    entries = []
    for number, line in enumerate(text.splitlines(), 1):
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if len(fields) < 2:
            raise ValueError(f"links.txt line {number}: need a repo path and an install path")
        entries.append(Entry(fields[0], fields[1]))
    return entries


def run(manifest: str, mode: str = "link", out: Callable[[str], None] = print) -> int:
    """Create missing links (mode "link") or only report (mode "check").

    Returns 0 when every entry is in the expected state, 1 otherwise.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode '{mode}'")

    repo = os.path.dirname(os.path.realpath(manifest))
    with open(manifest, encoding="utf-8") as f:
        entries = parse_manifest(f.read())

    rc = 0
    for entry in entries:
        src = os.path.join(repo, entry.name)
        dst = os.path.expanduser(entry.target)

        if not os.path.exists(src):
            out(f"MISSING-SRC  {src}")
            rc = 1
        elif os.path.islink(dst):
            if os.path.realpath(dst) == os.path.realpath(src):
                out(f"ok           {dst}")
            else:
                out(f"WRONG-LINK   {dst} -> {os.readlink(dst)}")
                rc = 1
        elif os.path.lexists(dst):
            out(f"NOT-A-LINK   {dst} (real file or dir; move it into the repo, then re-run)")
            rc = 1
        elif mode == "link":
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.symlink(src, dst)
            out(f"linked       {dst} -> {src}")
        else:
            out(f"UNLINKED     {dst}")
            rc = 1
    return rc
