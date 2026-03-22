# archiveinator

A local, self-hosted web page archiver with ad blocking and paywall bypass.

## Problem Statement

Organizations face problems using archive.today. Its hosting is unstable and hosted in Russia. Its author is unknown and uses the Cloudflare captcha page to DDoS people.

## Solution

archiveinator runs locally in a lightweight way, giving you full control over your archives. It saves web pages as self-contained single-file HTML documents you can open offline forever, with no external dependencies.

## Features

- Creates self-contained `.html` archives viewable offline (via [monolith](https://github.com/Y2Z/monolith))
- Blocks ads at the network level (EasyList + EasyPrivacy) and cleans ad DOM elements after load
- Detects paywalls automatically and tries multiple bypass strategies in sequence
- Collapses responsive images to a single reasonable size before archiving
- Fully configurable pipeline — enable or disable any step in `config.yaml`

---

## Requirements

- Python 3.11 or later

The monolith binary, Playwright Chromium, and ad-blocking rule sets are all installed automatically by `archiveinator setup`.

---

## Installation

archiveinator is installed directly from the GitHub repository into a Python virtual environment. There is no PyPI package.

### Mac / Linux

```bash
# 1. Create a directory for archiveinator and a virtual environment inside it
mkdir archiveinator
cd archiveinator
python3 -m venv .venv
```

> **Using a specific Python version?** archiveinator requires Python 3.11+. If your system Python is older, you can point `venv` at a newer install:
>
> ```bash
> # Option A: pyenv
> brew install pyenv
> pyenv install 3.12
> ~/.pyenv/versions/3.12.*/bin/python3.12 -m venv .venv
>
> # Option B: Homebrew Python
> brew install python@3.12
> /opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
> ```
>
> Your system Python is untouched either way.

```bash
# 2. Activate it
source .venv/bin/activate

# 3. Install archiveinator
pip3 install git+https://github.com/p0rkchop/archiveinator.git
```

### Windows

```powershell
# 1. Create a directory for archiveinator and a virtual environment inside it
mkdir archiveinator
cd archiveinator
python -m venv .venv

# 2. Activate it
.venv\Scripts\activate.bat

# 3. Install archiveinator
pip3 install git+https://github.com/p0rkchop/archiveinator.git
```

> To uninstall, just delete the `archiveinator` folder — it contains everything.

---

## First-time Setup

With the virtual environment **active**, run the setup command once:

```bash
archiveinator setup
```

This will:

1. Create the default config file at the platform-appropriate path
2. Install Playwright's Chromium browser into the virtual environment
3. Download the monolith binary for your platform from the [latest release](https://github.com/p0rkchop/archiveinator/releases/latest)
4. Download EasyList and EasyPrivacy ad-blocking rule sets

> **macOS note:** If you have `monolith` installed via Homebrew, setup will detect and use it automatically.

---

## Upgrading

With the virtual environment active, run:

```bash
pip3 install --upgrade git+https://github.com/p0rkchop/archiveinator.git
```

Then re-run setup to update the monolith binary and blocklists:

```bash
archiveinator setup
```

---

## Activating and Deactivating

You need to activate the virtual environment each time you open a new terminal session before using archiveinator.

**Mac / Linux:**
```bash
# Activate (from inside your archiveinator directory)
source .venv/bin/activate

# Your prompt will change to show the venv is active, e.g.:
# (.venv) $

# Deactivate when done
deactivate
```

**Windows:**
```powershell
# Activate (from inside your archiveinator directory)
.venv\Scripts\activate.bat

# Deactivate when done
deactivate
```

Once activated, `archiveinator` is available as a command:

```bash
archiveinator archive https://example.com/article
```

---

## Usage

### Archive a URL

```bash
archiveinator archive <url>
```

The archive is saved as a self-contained `.html` file in your current directory (or the configured `output_dir`). The filename includes the date, hostname, and page title:

```
2026-03-21_14-30_example.com_article-title.html
```

**Examples:**

```bash
# Save to current directory
archiveinator archive https://example.com/article

# Save to a specific directory
archiveinator archive https://example.com/article --output-dir ~/archives

# Write HTML to stdout (status messages go to stderr)
archiveinator archive https://example.com/article --stdout

# Pipe to a file or another tool
archiveinator archive https://example.com/article --stdout > article.html

# Show verbose output (pipeline steps, paywall bypass attempts)
archiveinator archive https://example.com/article --verbose
```

**Options:**

| Flag | Short | Description |
|------|-------|-------------|
| `--output-dir PATH` | `-o` | Directory to save the archive (overrides config) |
| `--stdout` | `-s` | Write HTML to stdout; status messages go to stderr |
| `--verbose` | `-v` | Show pipeline step messages |

`--stdout` and `--output-dir` are mutually exclusive.

### Update ad-blocking rules

```bash
archiveinator update-blocklists
```

Downloads the latest EasyList and EasyPrivacy rules. Also runs automatically on a schedule via CI (every Monday at 03:00 UTC) if you fork the repository.

### Get help

```bash
archiveinator --help
archiveinator archive --help
```

---

## Paywall Bypass

archiveinator automatically detects paywalled pages and works through bypass strategies in sequence, stopping as soon as the page is accessible.

### Detection

A page is considered paywalled if any of the following are true:

- **HTTP status** is 401, 402, 403, or 429
- **DOM selectors** match known paywall elements (Piano/TinyPass modals, `.paywall`, `.content-gate`, `.tp-modal`, subscription walls, metered access overlays, and 30+ others)
- **Word count** is suspiciously low (< 150 words), indicating a teaser stub

### Bypass strategies (in order)

1. **JS overlay removal** — Removes paywall modal elements from the live page DOM and restores body scroll before the page is serialized. No reload required; fires while the browser is still open.

2. **UA cycling** — Retries the page load with the next user agent in the configured list. Requires `user_agents.cycle: true` in config. Successful agent/domain pairs are cached so future runs start with the known-good UA.

3. **Header tricks** — Retries with Googlebot user agent, `Referer: https://www.google.com/`, and `X-Forwarded-For: 66.249.66.1`. Many publishers allow Googlebot through paywalls to stay indexed.

4. **Google News referral** — Retries with Googlebot UA and `Referer: https://news.google.com/`, simulating a Google News click-through.

5. **Content extraction fallback** — If the page is still paywalled after all retries, [trafilatura](https://trafilatura.readthedocs.io/) extracts the article body from the available HTML. The archive is saved as a clean, readable document containing the article text.

If all strategies are exhausted without success, a partial archive of whatever HTML was retrieved is saved with `_partial` in the filename.

---

## Configuration

The config file is created automatically at first run.

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/archiveinator/config.yaml` |
| Linux | `~/.config/archiveinator/config.yaml` |
| Windows | `%APPDATA%\archiveinator\config.yaml` |

### Full config reference

```yaml
# Directory where archived files are saved (default: current working directory)
output_dir: .

# Maximum asset size to inline in MB (images, CSS, fonts — audio/video always skipped)
asset_size_limit_mb: 5

# Page load timeout in seconds
timeout_seconds: 30

# How often to auto-refresh adblock blocklists (in days)
blocklist_update_interval_days: 7

user_agents:
  # Set to true to enable UA cycling as a paywall bypass strategy
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
  - step: network_ad_blocking   # Block ad requests before they're made
    enabled: true
  - step: page_load             # Load page in headless Chromium
    enabled: true
  - step: paywall_detection     # Detect paywall (runs inside page_load)
    enabled: true
  - step: js_overlay_removal    # Remove paywall modals from live page
    enabled: true
  - step: ua_cycling            # Retry with next UA (requires cycle: true)
    enabled: true
  - step: header_tricks         # Retry with Googlebot UA + Google referer
    enabled: true
  - step: google_news           # Retry with Google News referer
    enabled: true
  - step: dom_ad_cleanup        # Remove ad DOM elements (runs inside page_load)
    enabled: true
  - step: image_dedup           # Collapse responsive images to one size
    enabled: true
  - step: content_extraction    # trafilatura fallback if still paywalled
    enabled: true
  - step: asset_inlining        # Inline all assets into single HTML (must be last)
    enabled: true
```

### Pipeline steps

| Step | Description |
|------|-------------|
| `network_ad_blocking` | Intercepts network requests and blocks ads/trackers using EasyList + EasyPrivacy rules before they're fetched |
| `page_load` | Loads the page in a headless Chromium browser and waits for network idle |
| `paywall_detection` | Detects paywalls via HTTP status, DOM selectors, and word count — runs inside the browser before serializing |
| `js_overlay_removal` | Removes JS-rendered paywall modals and overlays from the live DOM; restores body scroll |
| `ua_cycling` | Retries page load with the next configured user agent (requires `user_agents.cycle: true`) |
| `header_tricks` | Retries with Googlebot UA, Google referer, and X-Forwarded-For header |
| `google_news` | Retries with Google News referer and Googlebot UA |
| `dom_ad_cleanup` | Removes residual ad elements from the DOM (Google Ads, DFP slots, Taboola widgets, tracking pixels) |
| `image_dedup` | Collapses `<picture>` and `srcset` responsive images to a single URL ≤ 1200px wide to avoid duplicating assets |
| `content_extraction` | Last-resort: uses trafilatura to extract the article body if the page is still paywalled |
| `asset_inlining` | Inlines CSS, images, fonts, and scripts into a single self-contained HTML file using monolith |

`page_load` must always be present. `asset_inlining`, if included, must be last.

### Enabling UA cycling for paywall bypass

To enable user agent cycling:

```yaml
user_agents:
  cycle: true       # enable cycling
  agents:
    - name: chrome_desktop
      enabled: true
      ua: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..."
    - name: googlebot
      enabled: true   # enable Googlebot as a fallback UA
      ua: "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
```

Successful agent/domain pairs are cached at:

| Platform | Cache Path |
|----------|-----------|
| macOS | `~/Library/Application Support/archiveinator/ua_cache.yaml` |
| Linux | `~/.config/archiveinator/ua_cache.yaml` |
| Windows | `%APPDATA%\archiveinator\ua_cache.yaml` |

---

## Releases

Each release publishes platform-specific [monolith](https://github.com/Y2Z/monolith) binaries compiled from source. These are what `archiveinator setup` downloads automatically — you do not need to manage them yourself.

| Asset | Platform |
|-------|----------|
| `archiveinator-darwin-aarch64` | macOS Apple Silicon |
| `archiveinator-linux-x86_64` | Linux x86_64 |
| `archiveinator-linux-aarch64` | Linux aarch64 |
| `archiveinator-windows-x86_64.exe` | Windows x86_64 |

---

## Development

```bash
# Clone the repo
git clone https://github.com/p0rkchop/archiveinator.git
cd archiveinator

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Mac / Linux
.venv\Scripts\activate.bat       # Windows

# Install with dev dependencies
pip3 install -e ".[dev]"

# Run setup (installs Chromium, monolith, blocklists)
archiveinator setup

# Run tests
pytest tests/unit/

# Lint and type check
ruff check .
mypy archiveinator/

# Deactivate when done
deactivate
```

Integration tests require a network connection and a Playwright Chromium install (done by `archiveinator setup`):

```bash
pytest tests/integration/
```

---

## License

See [LICENSE](LICENSE).
