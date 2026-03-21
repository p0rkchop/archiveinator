from __future__ import annotations

from archiveinator import console


def test_configure_sets_verbose():
    console.configure(verbose=True, debug=False)
    assert console.is_verbose() is True
    assert console.is_debug() is False


def test_configure_sets_debug():
    console.configure(verbose=False, debug=True)
    assert console.is_debug() is True


def test_configure_defaults_to_false():
    console.configure()
    assert console.is_verbose() is False
    assert console.is_debug() is False


def test_configure_resets_state():
    console.configure(verbose=True, debug=True)
    console.configure()
    assert console.is_verbose() is False
    assert console.is_debug() is False
