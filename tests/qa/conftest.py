"""QA conftest — fixtures, CLI options, and dynamic parametrisation."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
import yaml

from tests.qa.reporter import print_summary, results

_SITES_YAML = Path(__file__).parent / "sites.yaml"


# ── pytest CLI options ──────────────────────────────────────────


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("qa", "archiveinator QA options")
    group.addoption(
        "--qa-paywall-type",
        help="Filter real-URL tests by paywall_type tag (e.g. piano, perimeter-x)",
    )
    group.addoption(
        "--qa-category",
        help="Filter real-URL tests by category tag (e.g. finance, tech, news)",
    )
    group.addoption(
        "--qa-difficulty",
        help="Filter real-URL tests by difficulty (easy | medium | hard)",
    )
    group.addoption(
        "--qa-sample",
        type=int,
        default=0,
        help="Run a random sample of N sites (0 = all matching)",
    )


# ── site catalog ────────────────────────────────────────────────


def _load_sites() -> list[dict]:
    """Load and return the site catalog from sites.yaml."""
    with open(_SITES_YAML) as f:
        data = yaml.safe_load(f)
    return data.get("sites", [])


def _filter_sites(sites: list[dict], config: pytest.Config) -> list[dict]:
    """Apply CLI filters to the site list."""
    pw_type = config.getoption("--qa-paywall-type", default=None)
    category = config.getoption("--qa-category", default=None)
    difficulty = config.getoption("--qa-difficulty", default=None)

    filtered = sites
    if pw_type:
        filtered = [s for s in filtered if s["tags"]["paywall_type"] == pw_type]
    if category:
        filtered = [s for s in filtered if s["tags"]["category"] == category]
    if difficulty:
        filtered = [s for s in filtered if s["tags"]["difficulty"] == difficulty]

    sample_size = config.getoption("--qa-sample", default=0)
    if sample_size and len(filtered) > sample_size:
        filtered = random.sample(filtered, sample_size)

    return filtered


# ── dynamic parametrisation for real-URL tests ──────────────────


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrise any test that requests the ``qa_site`` fixture."""
    if "qa_site" not in metafunc.fixturenames:
        return

    sites = _load_sites()
    filtered = _filter_sites(sites, metafunc.config)

    ids = [s["name"] for s in filtered]
    metafunc.parametrize("qa_site", filtered, ids=ids)


# ── summary hook ────────────────────────────────────────────────


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Print the rich QA summary table after all tests finish."""
    print_summary()
