---
layout: default
title: CLI Reference
nav_order: 3
---

# CLI Reference

All commands available in the archiveinator command-line interface.

---

## `archiveinator archive`

Archive a web page to a self-contained HTML file.

```bash
archiveinator archive <url>
```

### Options

| Flag | Short | Description |
|:-----|:------|:------------|
| `--output-dir PATH` | `-o` | Directory to save the archive (overrides config) |
| `--stdout` | `-s` | Write HTML to stdout; status messages go to stderr |
| `--json` | `-j` | Output JSON metadata to stdout |
| `--verbose` | `-v` | Show pipeline step messages and paywall bypass attempts |
| `--stealth` | | Force stealth browser mode (anti-fingerprinting) |
| `--cookies-file PATH` | `-c` | JSON file containing cookies for authentication |
| `--timeout SECONDS` | `-t` | Page load timeout in seconds (overrides config) |
| `--no-netblock` | | Disable network-level ad blocking for this run |
| `--no-dom-cleanup` | | Disable DOM ad node removal for this run |

`--stdout` and `--output-dir` are mutually exclusive.

### Cookie Formats

Cookie files can be in any of these formats (auto-detected):

- **Cookie-Editor**: `{ "cookies": [...] }`
- **EditThisCookie**: `[...]`
- **Playwright storage state**: Full storage state JSON

### Examples

```bash
# Basic archive
archiveinator archive https://example.com/article

# Save to a specific directory
archiveinator archive https://example.com/article -o ~/archives

# Verbose mode — see pipeline progress
archiveinator archive https://example.com/article -v

# With authentication cookies
archiveinator archive https://example.com/private -c cookies.json

# Force stealth browser (anti-fingerprinting)
archiveinator archive https://example.com/article --stealth

# Skip ad blocking for this run (useful when debugging)
archiveinator archive https://example.com/article --no-netblock --no-dom-cleanup
```

---

## `archiveinator setup`

Install required dependencies and create default configuration.

```bash
archiveinator setup
```

This installs:

1. **Playwright Chromium** — headless browser for page loading
2. **monolith binary** — for asset inlining (self-contained HTML)
3. **EasyList + EasyPrivacy** — ad-blocking rule sets for network filtering
4. **Default config file** — at the platform-appropriate path

{: .note }
Re-run `archiveinator setup` after upgrading to refresh the monolith binary and blocklists.

---

## `archiveinator login`

Launch an interactive browser to capture authentication cookies.

```bash
archiveinator login <url>
```

### Options

| Flag | Short | Description |
|:-----|:------|:------------|
| `--output PATH` | `-o` | Path to save the cookies JSON file (default: `cookies.json`) |
| `--headless` | | Run browser in headless mode (no visible window) |
| `--timeout SECONDS` | | Timeout before auto-closing the browser |
| `--full-storage` | | Save full Playwright storage state (cookies + localStorage) instead of just cookies |

### Examples

```bash
# Basic: opens browser, log in manually, close to save
archiveinator login https://example.com

# Headless with timeout (useful for automated flows)
archiveinator login https://example.com --headless --timeout 60

# Save full storage state
archiveinator login https://example.com --full-storage -o state.json
```

---

## `archiveinator serve`

Start the web UI server.

```bash
archiveinator serve
```

### Options

| Flag | Description |
|:-----|:------------|
| `--host HOST` | Bind address (default: `0.0.0.0` for Docker, `127.0.0.1` for local) |
| `--port PORT` | Port (default: `8080`) |
| `--dev` | Enable auto-reload, debug templates, and verbose logging |

### Examples

```bash
# Start on default port
archiveinator serve

# Custom host and port
archiveinator serve --host 0.0.0.0 --port 8080

# Development mode
archiveinator serve --dev
```

See the [Web UI Guide](web-ui/) for full documentation.

---

## `archiveinator ladder`

Start a [Ladder](https://github.com/everywall/ladder) HTTP proxy for paywall bypass research.

```bash
archiveinator ladder
```

Automatically pulls the Ladder Docker image and starts it on `localhost:8181`. Useful when investigating a new paywalled site — iterate on header/referrer combos with a quick `curl` instead of running the full Playwright pipeline each time. Requires Docker.

### Options

| Flag | Short | Description |
|:-----|:------|:------------|
| `--port PORT` | `-p` | Local port to bind Ladder to (default: `8181`) |
| `--rules PATH` | `-r` | Directory of YAML rule files (default: `{config_dir}/ladder-rules/`) |

### Endpoints

Once running, Ladder exposes three endpoints:

| Endpoint | Returns |
|:---------|:--------|
| `http://localhost:8181/<url>` | Proxied HTML page |
| `http://localhost:8181/api/<url>` | JSON `{ body, headers }` |
| `http://localhost:8181/raw/<url>` | Raw HTML string |

Ladder defaults to Googlebot UA + `X-Forwarded-For: 66.249.66.1` for all requests.

### YAML Rules

Drop `.yaml` files into the rules directory to apply per-site header overrides:

```yaml
# ~/.config/archiveinator/ladder-rules/nytimes.yaml
domains:
  - nytimes.com
rules:
  user_agent: "Mozilla/5.0 ..."
  referer: "https://news.google.com/"
  headers:
    X-Forwarded-For: "66.249.66.1"
```

### Examples

```bash
# Start with defaults
archiveinator ladder

# Test a URL through the proxy
curl http://localhost:8181/https://nytimes.com

# Get JSON with body + response headers
curl http://localhost:8181/api/https://nytimes.com | jq '.body' | wc -w

# Custom port
archiveinator ladder --port 9090

# Custom rules directory
archiveinator ladder --rules ~/my-ladder-rules/
```

Press Ctrl+C to stop and remove the container.

---

## `archiveinator update-blocklists`

Download the latest ad-blocking rule sets.

```bash
archiveinator update-blocklists
```

Fetches the latest EasyList and EasyPrivacy rules. Also runs automatically on a schedule via CI (every Monday at 03:00 UTC) if you fork the repository.

---

## `archiveinator cache`

Manage the per-domain bypass strategy cache.

```bash
archiveinator cache list
archiveinator cache clear [--domain DOMAIN]
```

| Subcommand | Description |
|:-----------|:------------|
| `cache list` | Show all cached bypass strategies and their success counts |
| `cache clear` | Clear all cached entries |
| `cache clear --domain DOMAIN` | Clear the cached entry for one domain |

---

## `archiveinator --help`

```bash
# General help
archiveinator --help

# Command-specific help
archiveinator archive --help
archiveinator ladder --help
archiveinator login --help
archiveinator serve --help
```
