---
layout: default
title: Docker
nav_order: 8
---

# Docker

Archiveinator ships as a Docker image with Playwright Chromium, the monolith binary, and pre-downloaded adblock blocklists. No Python setup required.

---

## Pull the Image

```bash
docker pull ghcr.io/p0rkchop/archiveinator:latest
```

## Available Tags

| Tag | Description |
|:----|:------------|
| `latest` | Most recent stable release |
| `0` | Latest in the v0.x series |
| `0.9` | Latest in the v0.9.x series |
| `0.9.1` | Pinned to this exact release |

{: .note }
New images are published automatically with each release. Pin to a specific version tag for reproducible, controlled upgrades.

---

## Quick Start

### CLI: Archive a Page

```bash
docker run --rm \
  -v $(pwd):/output \
  ghcr.io/p0rkchop/archiveinator:latest \
  archive https://example.com/article
```

The archived HTML file appears in your current directory.

### Web UI: Start the Server

```bash
docker run --rm \
  -p 8080:8080 \
  -v archive-data:/data \
  ghcr.io/p0rkchop/archiveinator:latest
```

Open [http://localhost:8080](http://localhost:8080) and register a new account.

{: .note }
The Docker image starts the web server by default (CMD `serve`). The ENTRYPOINT is `archiveinator`, so you can run any CLI command after the image name.

---

## Volume Mounts

| Path | Purpose | Recommended |
|:-----|:--------|:------------|
| `/output` | Where archived HTML files are saved | Mount for CLI use |
| `/config` | Config directory — mounts a `config.yaml` for custom settings | Optional (auto-created) |
| `/data` | SQLite database, archives, and caches | **Persist this** for Web UI |

### Full Example

```bash
docker run --rm \
  -p 8080:8080 \
  -v ~/archives:/output \
  -v ~/.archiveinator-config:/config \
  -v archive-data:/data \
  -e RESEND_API_KEY=re_xxx \
  ghcr.io/p0rkchop/archiveinator:0.9.1
```

---

## Web UI with Docker

The web UI is included in the image and starts by default:

```bash
# Basic
docker run --rm -p 8080:8080 -v archive-data:/data ghcr.io/p0rkchop/archiveinator:latest

# With email notifications
docker run --rm \
  -p 8080:8080 \
  -v archive-data:/data \
  -e RESEND_API_KEY=re_xxx \
  ghcr.io/p0rkchop/archiveinator:latest
```

### Environment Variables

| Variable | Default | Description |
|:---------|:--------|:------------|
| `RESEND_API_KEY` | _(none)_ | [Resend](https://resend.com) API key for email notifications. If unset, email sending is silently skipped |
| `FLARESOLVERR_URL` | _(none)_ | URL of a running FlareSolverr instance for Cloudflare IUAM bypass (e.g. `http://flaresolverr:8191/v1`). Only needed for Cloudflare-protected sites |

---

## FlareSolverr for Cloudflare Sites

[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) is an optional sidecar that solves Cloudflare IUAM and Turnstile challenges. Run it alongside archiveinator for better success on Cloudflare-protected sites:

```yaml
# docker-compose.yml
services:
  archiveinator:
    image: ghcr.io/p0rkchop/archiveinator:latest
    ports:
      - "8080:8080"
    volumes:
      - archive-data:/data
    environment:
      - FLARESOLVERR_URL=http://flaresolverr:8191/v1
    depends_on:
      - flaresolverr

  flaresolverr:
    image: ghcr.io/flaresolverr/flaresolverr:latest
    environment:
      - LOG_LEVEL=info

volumes:
  archive-data:
```

```bash
docker compose up -d
```

Without FlareSolverr, the `flaresolverr` pipeline step is a complete no-op — no errors, just skipped.

---

## Scripting with Docker

### Archive a List of URLs

```bash
while read -r url; do
  docker run --rm -v ~/archives:/output ghcr.io/p0rkchop/archiveinator:latest archive "$url"
done < urls.txt
```

### Capture Cookies via Interactive Login

```bash
docker run --rm -it \
  -v ~/archives:/output \
  ghcr.io/p0rkchop/archiveinator:latest \
  login https://example.com -o /output/cookies.json
```

---

## Building from Source

```bash
# From the repo root
docker build -t archiveinator:custom .

# With a specific release ref
docker build --build-arg RELEASE_REF=v0.9.1 -t archiveinator:custom .
```

---

## Upgrading

```bash
docker pull ghcr.io/p0rkchop/archiveinator:latest
```

Or pull a specific version:

```bash
docker pull ghcr.io/p0rkchop/archiveinator:0.9.1
```
