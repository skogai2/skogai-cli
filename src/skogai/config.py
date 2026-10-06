"""Layered config: base defaults, then machine, then repo. Later layers win.

Layers, lowest to highest (docs/CONFIG.md):
  base          config.defaults.json in the store (pinned dash-skogai commit)
  machine       $SKOGAI_CONFIG_JSON_FILE, else $XDG_CONFIG_HOME/skogai/config.json
  machine.local the same directory, config.local.json
  repo          <store>/config.json (also holds the base pin)
  repo.local    <store>/config.local.json

Objects merge key by key. Arrays and scalars are replaced whole, so a value
always comes from exactly one layer, and --source can name it.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from skogai.store import DEFAULTS_NAME, read_file

LAYER_ORDER = ("base", "machine", "machine.local", "repo", "repo.local")
SECRET_KEY = re.compile(r"(TOKEN|KEY|PASSWORD|SECRET)$", re.IGNORECASE)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Layer:
    name: str
    path: str
    data: dict  # empty when the file is absent


def machine_config_path(env: Mapping[str, str]) -> str:
    if env.get("SKOGAI_CONFIG_JSON_FILE"):
        return os.path.normpath(os.path.expanduser(env["SKOGAI_CONFIG_JSON_FILE"]))
    base = env.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "skogai", "config.json")


def _local(path: str) -> str:
    root, ext = os.path.splitext(path)
    return f"{root}.local{ext}"


def _load(name: str, path: str) -> Layer:
    raw = read_file(path)
    if raw is None:
        return Layer(name, path, {})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} is not valid JSON: {e}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a JSON object")
    return Layer(name, path, data)


def load_layers(store: str, env: Mapping[str, str]) -> list[Layer]:
    machine = machine_config_path(env)
    layers = [
        _load("base", os.path.join(store, DEFAULTS_NAME)),
        _load("machine", machine),
        _load("machine.local", _local(machine)),
        _load("repo", os.path.join(store, "config.json")),
        _load("repo.local", os.path.join(store, "config.local.json")),
    ]
    for layer in layers:
        _refuse_secrets(layer)
    return layers


def _leaves(data, prefix: str = ""):
    """Yield (dotted key, value) for every leaf. Arrays are leaves."""
    if isinstance(data, dict):
        for key, value in data.items():
            yield from _leaves(value, f"{prefix}.{key}" if prefix else key)
    elif prefix:
        yield prefix, data


def _refuse_secrets(layer: Layer) -> None:
    for key, _ in _leaves(layer.data):
        last = key.rsplit(".", 1)[-1]
        if SECRET_KEY.search(last):
            raise ConfigError(
                f"{layer.path}: '{key}' looks like a secret. Secrets never go in config files"
            )


def merged(layers: list[Layer]) -> dict:
    result: dict = {}
    for layer in layers:
        _deep_merge(result, layer.data)
    return result


def _deep_merge(target: dict, source: dict) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def sources(layers: list[Layer]) -> dict[str, tuple[object, str]]:
    """Map each dotted leaf of the merged config to (value, layer that set it).

    Walks the merged result, so a value replaced by a higher layer does not
    keep a stale entry from a lower one.
    """
    per_layer = [(layer.name, dict(_leaves(layer.data))) for layer in layers]
    where: dict[str, tuple[object, str]] = {}
    for key, value in _leaves(merged(layers)):
        setter = None
        for name, leaves in per_layer:
            if key in leaves:
                setter = name
        where[key] = (value, setter)
    return where


def get(layers: list[Layer], key: str | None) -> list[tuple[str, object, str]]:
    """Leaves at or under key, as (dotted key, value, layer name), sorted."""
    where = sources(layers)
    if key is None:
        return [(k, v, src) for k, (v, src) in sorted(where.items())]
    prefix = key + "."
    hits = [(k, v, src) for k, (v, src) in sorted(where.items()) if k == key or k.startswith(prefix)]
    return hits


def layer_value(layers: list[Layer], name: str, key: str | None):
    """Raw values from one layer, for key or the whole layer when key is None."""
    layer = next((l for l in layers if l.name == name), None)
    if layer is None:
        raise ConfigError(f"unknown layer '{name}' (layers: {', '.join(LAYER_ORDER)})")
    if key is None:
        return layer.data
    value = layer.data
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value
