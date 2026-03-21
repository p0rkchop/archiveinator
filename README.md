# archiveinator

A local, self-hosted web page archiver with ad blocking and paywall bypass.

## Problem Statement

Organizations face problems using archive.today. Its hosting is unstable and hosted in Russia. Its author is unknown and uses the Cloudflare captcha page to DDoS people.

## Solution

archiveinator runs locally in a lightweight way, giving you full control over your archives.

## Features

- Creates a self-contained local copy of a web page viewable offline
- Blocks advertisements at the network and DOM level
- Employs methods to bypass paywalls whenever possible

---

## Requirements

- Python 3.11 or later
- pip / pipx (or uv)

---

## Installation

### Mac

```bash
# 1. Install monolith (required for asset inlining)
brew install monolith

# 2. Install archiveinator
pip install archiveinator
# or, to isolate it from system Python:
pipx install archiveinator
```

### Linux

```bash
# Install archiveinator (monolith is downloaded automatically during setup)
pip install archiveinator
# or:
pipx install archiveinator
```

### Windows

```powershell
# Install archiveinator (monolith is downloaded automatically during setup)
pip install archiveinator
# or:
pipx install archiveinator
```

---

## First-time Setup

After installation, run the setup command once. It will:

1. Create the default config file
2. Install Playwright's Chromium browser
3. Install or download the monolith binary
4. Download EasyList and EasyPrivacy ad-blocking rule sets

```bash
archiveinator setup
```

> **Mac note:** If you installed monolith via Homebrew before running setup, it will be detected and used automatically — no download needed.

---

## Usage

### Archive a URL

```bash
archiveinator archive <url>
```

The archive is saved as a self-contained `.html` file in your current directory (or the configured output directory).

**Examples:**

```bash
# Basic archive
archiveinator archive https://example.com/article

# Save to a specific directory
archiveinator archive https://example.com/article --output-dir ~/archives

# Verbose output (shows pipeline steps and debug info)
archiveinator archive https://example.com/article --verbose
```

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--output-dir PATH` | `-o` | Directory to save the archive (overrides config) |
| `--verbose` | `-v` | Show verbose/debug output |

### Get help

```bash
archiveinator --help
archiveinator archive --help
```

---

## Configuration

The config file is created automatically at first run. Its location depends on your platform:

| Platform | Path |
|----------|------|
| Mac | `~/Library/Application Support/archiveinator/config.yaml` |
| Linux | `~/.config/archiveinator/config.yaml` |
| Windows | `%APPDATA%\archiveinator\config.yaml` |

### Default config

```yaml
# Directory where archived files are saved (default: current working directory)
output_dir: .

# Maximum asset size to inline in MB (images, CSS, fonts — videos are always skipped)
asset_size_limit_mb: 5

# Page load timeout in seconds
timeout_seconds: 30

# How often to auto-update adblock blocklists (in days)
blocklist_update_interval_days: 7

user_agents:
  cycle: false
  agents:
    - name: chrome_desktop
      enabled: true
      ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    - name: googlebot
      enabled: false
      ua: "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    - name: bingbot
      enabled: false
      ua: "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingcrawl.htm)"

pipeline:
  - step: network_ad_blocking
    enabled: true
  - step: page_load
    enabled: true
  - step: dom_ad_cleanup
    enabled: true
  - step: asset_inlining
    enabled: true
```

### Pipeline steps

| Step | Description |
|------|-------------|
| `network_ad_blocking` | Blocks ad/tracker requests at the network level using EasyList rules |
| `page_load` | Loads the page in a headless Chromium browser |
| `dom_ad_cleanup` | Removes ad elements from the DOM after load |
| `asset_inlining` | Inlines all assets (images, CSS, fonts) into a single HTML file |

`page_load` must always be present. `asset_inlining`, if included, must be the last step.

---

## Development

```bash
# Clone the repo
git clone https://github.com/p0rkchop/archiveinator.git
cd archiveinator

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # Mac / Linux
.venv\Scripts\activate         # Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Run setup
archiveinator setup

# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy archiveinator
```

---

## License

See [LICENSE](LICENSE).
