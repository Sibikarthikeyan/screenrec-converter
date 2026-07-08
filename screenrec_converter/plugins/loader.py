"""Discover and instantiate plugins named in the config."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import sys
from pathlib import Path

from ..config import AppConfig, config_path
from .base import Plugin

log = logging.getLogger(__name__)


def _user_plugin_dir() -> Path:
    return config_path().parent / "plugins"


def _classes_in_module(module) -> dict[str, type[Plugin]]:
    return {
        name: obj
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, Plugin) and obj is not Plugin
    }


def _discover() -> dict[str, type[Plugin]]:
    found: dict[str, type[Plugin]] = {}

    # Built-in plugins: modules in this package (other than base/loader).
    pkg_dir = Path(__file__).parent
    for py in pkg_dir.glob("*.py"):
        if py.stem in {"__init__", "base", "loader"}:
            continue
        module = importlib.import_module(f"{__package__}.{py.stem}")
        found.update(_classes_in_module(module))

    # User plugins: standalone .py files in the config dir.
    user_dir = _user_plugin_dir()
    if user_dir.is_dir():
        for py in sorted(user_dir.glob("*.py")):
            mod_name = f"screenrec_user_plugin_{py.stem}"
            try:
                spec = importlib.util.spec_from_file_location(mod_name, py)
                assert spec and spec.loader
                module = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = module
                spec.loader.exec_module(module)
                found.update(_classes_in_module(module))
            except Exception:
                log.exception("Failed to load user plugin %s", py)

    return found


def load_plugins(cfg: AppConfig) -> list[Plugin]:
    if not cfg.enabled_plugins:
        return []
    available = _discover()
    plugins: list[Plugin] = []
    for name in cfg.enabled_plugins:
        cls = available.get(name)
        if cls is None:
            log.warning("Enabled plugin %r not found (available: %s)",
                        name, ", ".join(sorted(available)) or "none")
            continue
        try:
            plugins.append(cls(cfg))
            log.info("Loaded plugin: %s", name)
        except Exception:
            log.exception("Failed to instantiate plugin %s", name)
    return plugins
