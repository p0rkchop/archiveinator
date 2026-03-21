from __future__ import annotations

from pathlib import Path

import adblock

from archiveinator.blocklist import (
    _build_engine,
    _read_filter_file,
    load_engine,
    should_block,
)


def _engine_from_rules(rules: list[str]) -> adblock.Engine:
    return _build_engine(rules)


# --- should_block ---


def test_should_block_known_ad_domain():
    engine = _engine_from_rules(["||ads.example.com^"])
    assert should_block(
        engine, "https://ads.example.com/banner.js", "https://example.com", "script"
    )


def test_should_not_block_safe_domain():
    engine = _engine_from_rules(["||ads.example.com^"])
    assert not should_block(
        engine, "https://safe.example.com/style.css", "https://example.com", "stylesheet"
    )


def test_should_block_builtin_doubleclick():
    engine = load_engine()  # uses built-in rules when no EasyList downloaded
    assert should_block(engine, "https://doubleclick.net/ad.js", "https://example.com", "script")


def test_should_block_builtin_googlesyndication():
    engine = load_engine()
    assert should_block(
        engine,
        "https://googlesyndication.com/pagead/js/adsbygoogle.js",
        "https://example.com",
        "script",
    )


def test_should_block_returns_false_on_exception():
    # Empty engine with no rules — should not raise
    engine = _engine_from_rules([])
    result = should_block(engine, "https://example.com", "https://example.com", "script")
    assert result is False


# --- _read_filter_file ---


def test_read_filter_file_skips_comments(tmp_path: Path):
    f = tmp_path / "list.txt"
    f.write_text("! This is a comment\n[Adblock Plus]\n||ads.example.com^\n")
    rules = _read_filter_file(f)
    assert rules == ["||ads.example.com^"]


def test_read_filter_file_skips_blank_lines(tmp_path: Path):
    f = tmp_path / "list.txt"
    f.write_text("\n||ads.example.com^\n\n||tracker.example.com^\n")
    rules = _read_filter_file(f)
    assert rules == ["||ads.example.com^", "||tracker.example.com^"]


def test_read_filter_file_handles_encoding_errors(tmp_path: Path):
    f = tmp_path / "list.txt"
    f.write_bytes(b"||ads.example.com^\n\xff\xfe||bad.bytes^\n")
    rules = _read_filter_file(f)
    assert any("ads.example.com" in r for r in rules)


# --- load_engine uses files when present ---


def test_load_engine_uses_easylist_file(tmp_path: Path, monkeypatch: object) -> None:
    import archiveinator.blocklist as bl

    assert isinstance(monkeypatch, object)

    easylist = tmp_path / "easylist.txt"
    easylist.write_text("||custom-ad-domain.example.com^\n")

    monkeypatch.setattr(bl, "_EASYLIST_PATH", easylist)
    monkeypatch.setattr(bl, "_EASYPRIVACY_PATH", tmp_path / "missing.txt")

    engine = bl.load_engine()
    assert should_block(
        engine, "https://custom-ad-domain.example.com/ad.js", "https://example.com", "script"
    )


def test_load_engine_falls_back_to_builtin_when_no_files(
    tmp_path: Path, monkeypatch: object
) -> None:
    import archiveinator.blocklist as bl

    monkeypatch.setattr(bl, "_EASYLIST_PATH", tmp_path / "missing1.txt")
    monkeypatch.setattr(bl, "_EASYPRIVACY_PATH", tmp_path / "missing2.txt")

    engine = bl.load_engine()
    # Built-in rules should still block doubleclick
    assert should_block(engine, "https://doubleclick.net/ad.js", "https://example.com", "script")
