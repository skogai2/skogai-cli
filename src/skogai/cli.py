"""The skogai command. Each module of the CLI is a subcommand here."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence

from skogai import config, install, links, store
from skogai.env import AREAS, check, resolve
from skogai.env.inventory import atuin_var_names, relevant
from skogai.source import DASH_SKOGAI_URL, GitSource, SourceError

COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _cmd_path(args: argparse.Namespace) -> int:
    if args.area is None and args.components:
        print("skogai path: components need an area", file=sys.stderr)
        return 2
    for c in args.components:
        if not COMPONENT.match(c):
            print(f"skogai path: bad component '{c}'", file=sys.stderr)
            return 2
    area = args.area.upper() if args.area is not None else None
    print(resolve(area, args.components).path)
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
    return _with_source(
        args, lambda s, src, ref: store.init(s, src, ref, apply=args.apply)
    )


def _cmd_update(args: argparse.Namespace) -> int:
    return _with_source(
        args, lambda s, src, ref: store.update(s, src, ref, apply=args.apply)
    )


def _fmt(value) -> str:
    return value if isinstance(value, str) else json.dumps(value)


def _as_json(hits: list[tuple[str, object, str]], key: str | None):
    """Nest the leaves under key into one JSON value. A single leaf is its bare value."""
    if key is not None and len(hits) == 1 and hits[0][0] == key:
        return hits[0][1]
    base = key + "." if key else ""
    tree: dict = {}
    for leaf, value, _ in hits:
        parts = leaf[len(base):].split(".")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return tree


def _cmd_config_get(args: argparse.Namespace) -> int:
    if args.json and args.source:
        print("skogai config: --json and --source cannot be used together", file=sys.stderr)
        return 2
    try:
        if not os.path.exists(os.path.join(args.store, store.DEFAULTS_NAME)):
            raise store.StoreError(f"{args.store} has no {store.DEFAULTS_NAME}; run skogai init first")
        layers = config.load_layers(args.store, os.environ)
        if args.layer:
            value = config.layer_value(layers, args.layer, args.key)
            if value is None:
                print(f"skogai config: {args.key} is not set in layer '{args.layer}'", file=sys.stderr)
                return 1
            print(json.dumps(value, indent=2) if args.json else _fmt(value))
            return 0

        hits = config.get(layers, args.key)
    except (OSError, store.StoreError, config.ConfigError) as e:
        print(f"skogai config: {e}", file=sys.stderr)
        return 2

    if not hits:
        print(f"skogai config: {args.key or 'config'} is not set", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(_as_json(hits, args.key), indent=2))
        return 0
    single = len(hits) == 1 and hits[0][0] == args.key
    for key, value, layer in hits:
        tail = f"\t[{layer}]" if args.source else ""
        if single:
            print(f"{_fmt(value)}{tail}")
        else:
            print(f"{key} = {_fmt(value)}{tail}")
    return 0


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
    sub = parser.add_subparsers(title="Commands", dest="command", required=True)

    p_path = sub.add_parser(
        "path",
        help="print the resolved path for an area, without a trailing slash",
    )
    p_path.add_argument("area", nargs="?", type=str.lower, choices=sorted(a.lower() for a in AREAS),
                        help="area to print, e.g. config, claude")
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

    p_init = sub.add_parser(
        "init",
        help="copy the shared defaults from dash-skogai into a store, dry run unless --apply",
    )
    _add_store_args(p_init)
    p_init.add_argument("--apply", action="store_true", help="write the store")
    p_init.set_defaults(func=_cmd_init)

    p_update = sub.add_parser(
        "update",
        help="move a store to another dash-skogai commit, dry run unless --apply",
    )
    _add_store_args(p_update)
    p_update.add_argument("--apply", action="store_true", help="write the changes")
    p_update.set_defaults(func=_cmd_update)

    p_install = sub.add_parser(
        "install",
        help="copy managed files from the store to their install paths, dry run unless --apply",
    )
    p_install.add_argument("--store", default=".skogai", help="store directory (default: ./.skogai)")
    p_install.add_argument("--apply", action="store_true", help="write the changes")
    p_install.set_defaults(func=_cmd_install)

    p_config = sub.add_parser("config", help="read the layered config")
    config_sub = p_config.add_subparsers(title="Commands", dest="config_command", required=True)
    p_get = config_sub.add_parser(
        "get",
        help="print a value, or every value when no key is given",
    )
    p_get.add_argument("key", nargs="?", help="dotted key, e.g. base.sha")
    p_get.add_argument("--store", default=".skogai", help="store directory (default: ./.skogai)")
    p_get.add_argument("--source", action="store_true", help="also print the layer that set it")
    p_get.add_argument("--layer", choices=config.LAYER_ORDER,
                       help="print the raw value from one layer instead")
    p_get.add_argument("--json", action="store_true",
                       help="print JSON, for scripts; cannot be combined with --source")
    p_get.set_defaults(func=_cmd_config_get)

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
