"""Install managed files from the store to their install paths.

Installs are copies, not links. The store holds the pinned version. The
install records the blob SHA it wrote in installs.json, so a later run can tell
an unchanged install from a local edit. Nothing that differs from the record is
overwritten. Those cases are reported as LOCAL-CHANGE.

Install directory lookup, most specific first (docs/CONFIG.md):
  1. the env variable named in install.env, if set
  2. $SKOGAI_CONFIG_EXAMPLE_DIR/<install.xdg>, if set: a sandbox config home,
     for tests and dry runs that must not touch the real config
  3. $XDG_CONFIG_HOME/<install.xdg>, if XDG_CONFIG_HOME is set
  4. install.default, with ~ expanded
"""

from __future__ import annotations

import os
import posixpath
from collections.abc import Mapping

from skogai.source import blob_sha
from skogai.store import (
    DEFAULTS_NAME,
    PINS_NAME,
    Out,
    StoreError,
    parse_defaults,
    store_path,
    read_file,
    read_json,
    write_file,
    write_json,
)

INSTALLS_NAME = "installs.json"


def install_dir(spec: dict, env: Mapping[str, str]) -> tuple[str, str]:
    """The directory a managed file installs into, and the tier that chose it."""
    if spec.get("env") and env.get(spec["env"]):
        return os.path.normpath(os.path.expanduser(env[spec["env"]])), "env"
    if env.get("SKOGAI_CONFIG_EXAMPLE_DIR"):
        path = os.path.join(env["SKOGAI_CONFIG_EXAMPLE_DIR"], spec.get("xdg", ""))
        return os.path.normpath(path), "example"
    if spec.get("xdg") and env.get("XDG_CONFIG_HOME"):
        path = os.path.join(env["XDG_CONFIG_HOME"], spec["xdg"])
        return os.path.normpath(path), "xdg"
    return os.path.normpath(os.path.expanduser(spec["default"])), "default"


def install(
    store: str,
    env: Mapping[str, str] | None = None,
    apply: bool = False,
    out: Out = print,
) -> int:
    """Show what installing would do. With apply, write the changes.

    Returns 0 when nothing is blocked, 1 when a local change blocks something.
    """
    env = os.environ if env is None else env

    defaults_raw = read_file(os.path.join(store, DEFAULTS_NAME))
    if defaults_raw is None:
        raise StoreError(f"{store} has no {DEFAULTS_NAME}; run skogai init first")
    entries = parse_defaults(defaults_raw)

    pins = dict(read_json(os.path.join(store, PINS_NAME)).get("files", {}))
    installs_path = os.path.join(store, INSTALLS_NAME)
    installs = read_json(installs_path) if os.path.exists(installs_path) else {}

    blocked = 0
    changed = 0
    for _, entry in sorted(entries.items()):
        # Pins, the store copy and the install record are all keyed by store path.
        dest = store_path(entry)
        spec = entry.get("install")
        if spec is None:
            out(f"SKIP         {dest}: no install path in config.defaults.json")
            continue

        stored = read_file(os.path.join(store, dest))
        if stored is None:
            out(f"LOCAL-CHANGE  {dest}: missing from the store, run skogai update")
            blocked += 1
            continue
        stored_id = blob_sha(stored)
        stored_mode = os.stat(os.path.join(store, dest)).st_mode & 0o777
        if pins.get(dest) != stored_id:
            out(f"LOCAL-CHANGE  {dest}: the store copy differs from its pin, left untouched")
            blocked += 1
            continue

        directory, tier = install_dir(spec, env)
        target = os.path.join(directory, posixpath.basename(dest))
        record = installs.get(dest)
        if record and record["path"] != target:
            out(f"NOTE         {dest} was installed at {record['path']}, that copy is left in place")
            record = None

        existing = read_file(target)
        mode_ok = existing is not None and os.stat(target).st_mode & 0o777 == stored_mode
        if existing is None:
            action = "INSTALL"
        elif blob_sha(existing) == stored_id:
            # Same content. Only the record or the mode may need fixing.
            if record and record["blob"] == stored_id:
                if mode_ok:
                    continue
                action = "MODE"
            else:
                action = "RECORD"
        elif record and blob_sha(existing) == record["blob"]:
            action = "UPDATE"
        else:
            out(f"LOCAL-CHANGE  {target}: differs from the store copy and from any copy skogai installed, left untouched")
            blocked += 1
            continue

        out(f"{action:<12} {target}  [{tier}]")
        changed += 1
        if apply:
            write_file(target, stored, stored_mode)
            installs[dest] = {"path": target, "blob": stored_id}

    if apply:
        write_json(installs_path, installs)
    if not apply and changed:
        out(f"{changed} change(s), dry run, pass --apply to write")
    if blocked:
        out(f"{blocked} file(s) with local changes were not touched")
        return 1
    if not changed:
        out("up to date")
    return 0
