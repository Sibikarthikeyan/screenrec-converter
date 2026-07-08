from __future__ import annotations

import textwrap

import screenrec_converter.plugins.loader as loader
from screenrec_converter.plugins import load_plugins


def test_no_plugins_enabled(cfg):
    assert load_plugins(cfg) == []


def test_unknown_plugin_is_skipped(cfg, caplog):
    cfg.enabled_plugins = ["DoesNotExist"]
    assert load_plugins(cfg) == []
    assert "not found" in caplog.text


def test_user_plugin_discovery(cfg, tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "greeter.py").write_text(textwrap.dedent("""
        from screenrec_converter.plugins import Plugin

        class Greeter(Plugin):
            def on_conversion_success(self, result):
                pass
    """))
    monkeypatch.setattr(loader, "_user_plugin_dir", lambda: plugin_dir)

    cfg.enabled_plugins = ["Greeter"]
    plugins = load_plugins(cfg)
    assert len(plugins) == 1
    assert type(plugins[0]).__name__ == "Greeter"
    assert plugins[0].cfg is cfg


def test_broken_user_plugin_does_not_crash_loader(cfg, tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "broken.py").write_text("raise RuntimeError('boom at import')")
    monkeypatch.setattr(loader, "_user_plugin_dir", lambda: plugin_dir)

    cfg.enabled_plugins = ["Anything"]
    assert load_plugins(cfg) == []
