![archiveinator](archiveinator-bannerinator.png)

# archiveinator

A local, self-hosted web page archiver with ad blocking and paywall bypass.

---

## Quick Install

```bash
# Clone and install
git clone https://github.com/p0rkchop/archiveinator.git
cd archiveinator
python3 -m venv .venv
source .venv/bin/activate
pip3 install git+https://github.com/p0rkchop/archiveinator.git
archiveinator setup
```

Or with Docker — no Python required:

```bash
docker pull ghcr.io/p0rkchop/archiveinator:latest
```

---

## Quick Start

```bash
# Archive a page
archiveinator archive https://example.com/article

# Start the web UI
archiveinator serve

# Docker one-liner
docker run --rm -v $(pwd):/output ghcr.io/p0rkchop/archiveinator:latest archive https://example.com
```

Web UI: open [http://localhost:8080](http://localhost:8080), register an account, and archive from your browser.

Docker web UI: `docker run --rm -p 8080:8080 -v archive-data:/data ghcr.io/p0rkchop/archiveinator:latest`

---

## Documentation

Full documentation at **[p0rkchop.github.io/archiveinator](https://p0rkchop.github.io/archiveinator/)**:

- [Getting Started](https://p0rkchop.github.io/archiveinator/getting-started) — prerequisites, installation, first archive
- [CLI Reference](https://p0rkchop.github.io/archiveinator/cli-reference) — all commands and options
- [Configuration](https://p0rkchop.github.io/archiveinator/configuration) — full config.yaml reference
- [Pipeline](https://p0rkchop.github.io/archiveinator/pipeline) — all 11 pipeline steps explained
- [Paywall Bypass](https://p0rkchop.github.io/archiveinator/paywall-bypass) — detection + 5 bypass strategies
- [Web UI](https://p0rkchop.github.io/archiveinator/web-ui/) — browser-based interface guide
- [Docker](https://p0rkchop.github.io/archiveinator/docker) — pull, run, volumes, scripting
- [Development](https://p0rkchop.github.io/archiveinator/development) — dev setup, testing, CI

---

## License

See [LICENSE](LICENSE).
