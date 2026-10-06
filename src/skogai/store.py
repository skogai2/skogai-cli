"""The repo's skogai store (default ./.skogai): init and update.

Store layout:
  config.json          base pin: where the defaults came from (layered config comes later)
  config.defaults.json copy of dash-skogai's config.defaults.json at the pinned commit
  pins.json            git blob SHA of each managed file as it was installed
  <source path>        the managed files, e.g. fish/config.fish

A managed file is only replaced if its local blob still matches the pin.
Anything else is reported as LOCAL-CHANGE and left alone.
"""

from __future__ import annotations

import difflib
import json
import os
import posixpath
from collections.abc import Callable

from skogai.source import GitSource, blob_sha

DEFAULTS_PATH = "config.defaults.json"
CONFIG_NAME = "config.json"
DEFAULTS_NAME = "config.defaults.json"
PINS_NAME = "pins.json"

Out = Callable[[str], None]


class StoreError(Exception):
    pass


def _safe_path(path: str) -> str:
    if not isinstance(path, str) or not path:
        raise StoreError(f"managed file path must be a non-empty string: {path!r}")
    if path.startswith("/") or ".." in path.split("/") or posixpath.normpath(path) != path:
        raise StoreError(f"managed file path must be relative and normalised: {path}")
    return path


def _check_install(src: str, install) -> None:
    if not isinstance(install, dict) or not isinstance(install.get("default"), str):
        raise StoreError(f"{src}: install needs a \"default\" path")
    for key in ("env", "xdg", "default"):
        if key in install and not isinstance(install[key], str):
            raise StoreError(f"{src}: install.{key} must be a string")
    if "xdg" in install:
        _safe_path(install["xdg"])


def parse_defaults(raw: bytes) -> dict[str, dict]:
    """Managed files from config.defaults.json, keyed by source path."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise StoreError(f"config.defaults.json is not valid JSON: {e}") from None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, list):
        raise StoreError('config.defaults.json needs a "files" list')
    entries: dict[str, dict] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise StoreError("each entry in files must be an object")
        src = _safe_path(entry.get("source"))
        if entry.get("install") is not None:
            _check_install(src, entry["install"])
        entries[src] = entry
    return entries


def read_file(path: str) -> bytes | None:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


def write_file(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def write_json(path: str, data: dict) -> None:
    write_file(path, (json.dumps(data, indent=2) + "\n").encode())


def read_json(path: str) -> dict:
    raw = read_file(path)
    if raw is None:
        raise StoreError(f"{path} not found; run skogai init first")
    return json.loads(raw)


def init(store: str, source: GitSource, ref: str = "HEAD", out: Out = print) -> int:
    if os.path.exists(os.path.join(store, CONFIG_NAME)):
        raise StoreError(f"{store} is already initialised; use skogai update")

    sha = source.resolve(ref)
    defaults_raw = source.read(sha, DEFAULTS_PATH)
    sources = parse_defaults(defaults_raw)

    pins = {}
    for src in sources:
        data = source.read(sha, src)
        write_file(os.path.join(store, src), data)
        pins[src] = blob_sha(data)
        out(f"copied       {src}")

    write_file(os.path.join(store, DEFAULTS_NAME), defaults_raw)
    write_json(os.path.join(store, PINS_NAME), {"files": pins})
    write_json(os.path.join(store, CONFIG_NAME), {"base": {"url": source.url, "sha": sha}})
    out(f"initialised {store} at {sha[:12]}")
    return 0


def _diff(src: str, old: bytes | None, new: bytes) -> list[str]:
    a = (old or b"").decode(errors="replace").splitlines(keepends=True)
    b = new.decode(errors="replace").splitlines(keepends=True)
    return [
        line.rstrip("\n")
        for line in difflib.unified_diff(a, b, fromfile=f"a/{src}", tofile=f"b/{src}")
    ]


def update(
    store: str,
    source: GitSource,
    ref: str = "HEAD",
    apply: bool = False,
    out: Out = print,
) -> int:
    """Show what moving to ref would change. With apply, write the changes.

    Returns 0 when nothing is blocked, 1 when a local change blocks something.
    """
    base = read_json(os.path.join(store, CONFIG_NAME))
    pins_path = os.path.join(store, PINS_NAME)
    pins: dict[str, str] = dict(read_json(pins_path).get("files", {}))

    sha = source.resolve(ref)
    defaults_raw = source.read(sha, DEFAULTS_PATH)
    wanted = parse_defaults(defaults_raw)
    wanted_set = set(wanted)

    blocked = 0
    changed = 0
    for src in sorted(set(pins) | wanted_set):
        local_path = os.path.join(store, src)
        local = read_file(local_path)
        local_id = blob_sha(local) if local is not None else None
        pinned = pins.get(src)

        if pinned is None:
            if local is not None:
                if src in wanted_set:
                    out(f"LOCAL-CHANGE  {src}: exists but is not pinned, left untouched")
                    blocked += 1
                continue
            # Not pinned, not on disk: a new managed file.
            data = source.read(sha, src)
            out(f"ADD          {src}")
            changed += 1
            if apply:
                write_file(local_path, data)
                pins[src] = blob_sha(data)
            continue

        if local_id != pinned:
            out(f"LOCAL-CHANGE  {src}: differs from or is missing against the pinned version, left untouched")
            blocked += 1
            continue

        if src not in wanted_set:
            out(f"REMOVED      {src}: no longer in dash-skogai, left in place")
            continue

        data = source.read(sha, src)
        if blob_sha(data) == pinned:
            continue

        out(f"UPDATE       {src}")
        for line in _diff(src, local, data):
            out(f"  {line}")
        changed += 1
        if apply:
            write_file(local_path, data)
            pins[src] = blob_sha(data)

    if apply:
        write_json(pins_path, {"files": pins})
        if blocked == 0:
            write_file(os.path.join(store, DEFAULTS_NAME), defaults_raw)
            write_json(
                os.path.join(store, CONFIG_NAME),
                {"base": {"url": source.url, "sha": sha}},
            )
            out(f"now at {sha[:12]}")
        else:
            out(f"base not moved from {base['base']['sha'][:12]}: resolve the LOCAL-CHANGE lines first")
    else:
        out(f"target {sha[:12]}: {changed} change(s), dry run, pass --apply to write")

    if blocked:
        out(f"{blocked} managed file(s) with local changes were not touched")
        return 1
    return 0
