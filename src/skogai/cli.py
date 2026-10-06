"""The skogai command. Each module of the CLI is a subcommand here."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence

from skogai import install, links, store
from skogai.env import AREAS, check, resolve
from skogai.env.inventory import atuin_var_names, relevant
from skogai.source import DASH_SKOGAI_URL, GitSource, SourceError

COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _cmd_path(args: argparse.Namespace) -> int:
    if args.area is None and args.components:
        print("skogai path: components need an area", file=sys.stderr)
        return 2
    if args.area is not None and args.area not in AREAS:
        names = ", ".join(sorted(AREAS))
        print(f"skogai path: unknown area '{args.area}' (areas: {names})", file=sys.stderr)
        return 2
    for c in args.components:
        if not COMPONENT.match(c):
            print(f"skogai path: bad component '{c}'", file=sys.stderr)
            return 2
    print(resolve(args.area, args.components).path)
    return 0


def _cmd_env_explain() -> int:
    env = dict(os.environ)

    print("Variables")
    variables = relevant(env)
    if not variables:
        print("  (none set)")
    for name in sorted(variables):
        tier = "xdg" if name.startswith("XDG_") and not name.startswith("XDG_SKOGAI_") else "app"
        print(f"  {name} = {variables[name]}  [{tier}]")

    print("\nResolved")
    rows = [("(root)", resolve(None, (), env))]
    rows += [(area, resolve(area, (), env)) for area in sorted(AREAS)]
    width = max(len(label) for label, _ in rows)
    for label, res in rows:
        source = f"{res.tier}: {res.var}" if res.var else res.tier
        print(f"  {label:<{width}}  {res.path}  [{source}]")
    return 0


def _cmd_env_check() -> int:
    findings = check(dict(os.environ), atuin_var_names())
    for f in findings:
        print(f"{f.level:<8} {f.rule:<11} {f.message}")

    errors = sum(f.level == "error" for f in findings)
    warnings = len(findings) - errors
    if not findings:
        print("ok: no findings")
    elif errors:
        print(f"not ok: {errors} error(s), {warnings} warning(s)")
    else:
        print(f"ok with {warnings} warning(s)")
    return 1 if errors else 0


def _cmd_link(args: argparse.Namespace) -> int:
    try:
        return links.run(args.manifest, args.mode)
    except (OSError, ValueError) as e:
        print(f"skogai link: {e}", file=sys.stderr)
        return 2


def _with_source(args: argparse.Namespace, fn) -> int:
    try:
        with GitSource(args.source) as source:
            return fn(args.store, source, args.ref)
    except (OSError, SourceError, store.StoreError, ValueError) as e:
        print(f"skogai {args.command}: {e}", file=sys.stderr)
        return 2


def _cmd_init(args: argparse.Namespace) -> int:
    return _with_source(args, lambda s, src, ref: store.init(s, src, ref))


def _cmd_update(args: argparse.Namespace) -> int:
    return _with_source(
        args, lambda s, src, ref: store.update(s, src, ref, apply=args.apply)
    )


def _cmd_install(args: argparse.Namespace) -> int:
    try:
        return install.install(args.store, apply=args.apply)
    except (OSError, store.StoreError, ValueError) as e:
        print(f"skogai install: {e}", file=sys.stderr)
        return 2


def _add_store_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--store", default=".skogai", help="store directory (default: ./.skogai)")
    p.add_argument("--source", default=DASH_SKOGAI_URL,
                   help="git URL or local path of dash-skogai")
    p.add_argument("--ref", default="HEAD", help="commit to read (default: the default branch)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skogai", description="skogai command line")
    sub = parser.add_subparsers(dest="command", required=True)

    p_path = sub.add_parser(
        "path",
        help="print the resolved path for an area, without a trailing slash",
    )
    p_path.add_argument("area", nargs="?", type=str.upper, help="e.g. config, claude")
    p_path.add_argument("components", nargs="*", help="e.g. fish")
    p_path.set_defaults(func=_cmd_path)

    p_env = sub.add_parser("env", help="explain or check environment variables")
    p_env.add_argument("action", nargs="?", choices=["check"], help="check the environment")
    p_env.add_argument("--explain", action="store_true", help="show each variable and its tier")
    p_env.set_defaults(func=_cmd_env)

    p_link = sub.add_parser("link", help="link repo config into place, as listed in a manifest")
    p_link.add_argument("mode", nargs="?", default="link", choices=links.MODES,
                        help="link (default) creates missing links; check only reports")
    p_link.add_argument("--manifest", default="links.txt", help="manifest file (default: links.txt)")
    p_link.set_defaults(func=_cmd_link)

    p_init = sub.add_parser("init", help="copy the shared defaults from dash-skogai into a store")
    _add_store_args(p_init)
    p_init.set_defaults(func=_cmd_init)

    p_update = sub.add_parser(
        "update",
        help="move a store to another dash-skogai commit; dry run unless --apply",
    )
    _add_store_args(p_update)
    p_update.add_argument("--apply", action="store_true", help="write the changes")
    p_update.set_defaults(func=_cmd_update)

    p_install = sub.add_parser(
        "install",
        help="copy managed files from the store to their install paths; dry run unless --apply",
    )
    p_install.add_argument("--store", default=".skogai", help="store directory (default: ./.skogai)")
    p_install.add_argument("--apply", action="store_true", help="write the changes")
    p_install.set_defaults(func=_cmd_install)

    return parser


def _cmd_env(args: argparse.Namespace) -> int:
    if args.action == "check":
        return _cmd_env_check()
    if args.explain:
        return _cmd_env_explain()
    print("skogai env: give --explain or check", file=sys.stderr)
    return 2


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
