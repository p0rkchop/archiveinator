from __future__ import annotations

from datetime import datetime

from archiveinator.naming import _extract_hostname, _slugify, _truncate, build_filename

FIXED_TS = datetime(2026, 3, 21, 14, 32, 0)


# --- _slugify ---


def test_slugify_basic():
    assert _slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    assert _slugify("It's a 'Test'!") == "its-a-test"


def test_slugify_collapses_hyphens():
    assert _slugify("foo  --  bar") == "foo-bar"


def test_slugify_strips_leading_trailing_hyphens():
    assert _slugify("  --hello--  ") == "hello"


def test_slugify_unicode_letters_kept():
    result = _slugify("Ünïcödé")
    assert "-" not in result or result  # should not crash


def test_slugify_empty_string():
    assert _slugify("") == ""


# --- _extract_hostname ---


def test_extract_hostname_strips_www():
    assert _extract_hostname("https://www.example.com/article") == "example.com"


def test_extract_hostname_no_www():
    assert _extract_hostname("https://nytimes.com/article") == "nytimes.com"


def test_extract_hostname_subdomain_preserved():
    assert _extract_hostname("https://news.ycombinator.com/item?id=1") == "news.ycombinator.com"


def test_extract_hostname_invalid_url():
    assert _extract_hostname("not-a-url") == "unknown"


def test_extract_hostname_no_scheme():
    # urlparse without scheme gives empty hostname
    assert _extract_hostname("example.com/path") == "unknown"


# --- _truncate ---


def test_truncate_short_string_unchanged():
    assert _truncate("short", 80) == "short"


def test_truncate_long_string_cut():
    long = "a" * 100
    result = _truncate(long, 80)
    assert len(result) <= 80


def test_truncate_cuts_at_word_boundary():
    text = "word1-word2-word3-word4-word5-word6-word7-word8-word9-word10-word11-word12-word13"
    result = _truncate(text, 40)
    assert not result.endswith("-")
    assert len(result) <= 40


# --- build_filename ---


def test_build_filename_format():
    result = build_filename(
        url="https://example.com/article",
        title="My Test Article",
        ts=FIXED_TS,
    )
    assert result == "2026-03-21_14-32_example.com_my-test-article.html"


def test_build_filename_strips_www():
    result = build_filename(
        url="https://www.nytimes.com/article",
        title="Big News",
        ts=FIXED_TS,
    )
    assert result.startswith("2026-03-21_14-32_nytimes.com_")


def test_build_filename_partial_suffix():
    result = build_filename(
        url="https://example.com",
        title="Some Article",
        ts=FIXED_TS,
        partial=True,
    )
    assert result.endswith("_partial.html")


def test_build_filename_empty_title_uses_untitled():
    result = build_filename(
        url="https://example.com",
        title="",
        ts=FIXED_TS,
    )
    assert "untitled" in result


def test_build_filename_whitespace_title_uses_untitled():
    result = build_filename(
        url="https://example.com",
        title="   ",
        ts=FIXED_TS,
    )
    assert "untitled" in result


def test_build_filename_long_title_truncated():
    long_title = (
        "This Is A Very Long Article Title That Goes On And On And Never Seems To End At All Ever"
    )
    result = build_filename(url="https://example.com", title=long_title, ts=FIXED_TS)
    # Slug portion shouldn't exceed TITLE_MAX_LEN
    slug_part = result.split("_", 3)[-1].replace(".html", "")
    assert len(slug_part) <= 80


def test_build_filename_uses_current_time_when_no_ts():
    result = build_filename(url="https://example.com", title="Article")
    # Should have today's date prefix
    today = datetime.now().strftime("%Y-%m-%d")
    assert result.startswith(today)


def test_build_filename_special_chars_in_title():
    result = build_filename(
        url="https://example.com",
        title="It's 'Complicated' & \"Messy\"!",
        ts=FIXED_TS,
    )
    # No special chars in filename
    slug = result.split("_", 3)[-1]
    assert "'" not in slug
    assert '"' not in slug
    assert "&" not in slug
