---
layout: default
title: Getting Started
nav_order: 2
---

# Getting Started

Get archiveinator running on your machine and archive your first page.

---

## Prerequisites

- **Python 3.11 or later** — if your system Python is older, use [pyenv](https://github.com/pyenv/pyenv) or [Homebrew](https://brew.sh) to install a newer version alongside it
- **macOS or Linux** — Windows is not currently supported
- The monolith binary, Playwright Chromium, and ad-blocking rule sets are all installed automatically by `archiveinator setup`

---

## Installation

archiveinator is installed directly from the GitHub repository into a Python virtual environment.

```bash
# 1. Create a directory and virtual environment
mkdir archiveinator
cd archiveinator
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install archiveinator
pip3 install git+https://github.com/p0rkchop/archiveinator.git
```

{: .note }
> **Using a specific Python version?** Point `venv` at your preferred install:
> ```bash
> # pyenv
> ~/.pyenv/versions/3.12.*/bin/python3.12 -m venv .venv
>
> # Homebrew
> /opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
> ```

---

## Docker Quick Start

If you have Docker installed, this is the fastest way — no Python, virtual environments, or setup steps:

```bash
# Pull the image
docker pull ghcr.io/p0rkchop/archiveinator:latest

# Archive a page
docker run --rm -v $(pwd):/output ghcr.io/p0rkchop/archiveinator:latest archive https://example.com
```

See the [Docker Guide](docker) for full details on volume mounts, tags, and the web UI.

---

## First-time Setup

With the virtual environment **active**, run the setup command once:

```bash
archiveinator setup
```

This will:

1. Create the default config file at the platform-appropriate path
2. Install Playwright's Chromium browser
3. Install Patchright's CDP-patched Chromium (for PerimeterX/DataDome bypass)
4. Download Camoufox patched Firefox (for Cloudflare/fingerprint bypass)
5. Download the [monolith](https://github.com/Y2Z/monolith) binary for your platform
6. Download EasyList and EasyPrivacy ad-blocking rule sets

{: .note }
> **macOS users:** If you have `monolith` installed via Homebrew, setup will detect and use it automatically.

---

## Your First Archive

```bash
# Archive a page — saves to current directory
archiveinator archive https://example.com/article

# Save to a specific directory
archiveinator archive https://example.com/article --output-dir ~/archives

# Write to stdout (status goes to stderr)
archiveinator archive https://example.com/article --stdout > article.html
```

The archive is saved as a self-contained `.html` file:

```
2026-03-21_14-30_example.com_article-title.html
```

---

## Web UI

archiveinator includes a browser-based web interface:

```bash
# Install with web dependencies
pip3 install "archiveinator[web] @ git+https://github.com/p0rkchop/archiveinator.git"

# Start the server
archiveinator serve

# Development mode (auto-reload, verbose logging)
archiveinator serve --dev
```

Open [http://localhost:8080](http://localhost:8080) and register a new account. See the [Web UI Guide](web-ui/) for full documentation.

---

## Upgrading

With the virtual environment active:

```bash
pip3 install --upgrade git+https://github.com/p0rkchop/archiveinator.git
archiveinator setup  # re-download monolith and blocklists
```

---

## Uninstalling

Just delete the `archiveinator` directory — it contains everything.

---

## Next Steps

- [CLI Reference](cli-reference) — all commands and options
- [Configuration](configuration) — customize the pipeline, user agents, and timeouts
- [Pipeline](pipeline) — understand each pipeline step
- [Paywall Bypass](paywall-bypass) — how archiveinator defeats paywalls
