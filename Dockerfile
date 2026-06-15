# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

ARG RELEASE_REF=main
ENV XDG_CONFIG_HOME=/config
ENV XDG_DATA_HOME=/data

# Install archiveinator with web extras from GitHub
RUN pip3 install "archiveinator[web] @ git+https://github.com/p0rkchop/archiveinator.git@${RELEASE_REF}"

# Optional bypass enhancers (best-effort — packages may not exist on PyPI yet)
RUN pip3 install patchright camoufox || true

# Ensure Chromium matches the installed playwright pip package version.
# The base image ships an older playwright/chromium pair; pip may pull a
# newer playwright, so we re-install the matching browser.
RUN python3 -m playwright install chromium

# Install Patchright's CDP-patched Chromium (skip gracefully if not installed)
RUN python3 -m patchright install chromium || true

# Fetch Camoufox patched Firefox binary (skip gracefully if not installed)
RUN python3 -m camoufox fetch || true

# Install curl-impersonate (Linux x86_64 only; skip on arm64 — binary not distributed)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
      CURL_VER=0.6.1 && \
      curl -fsSL -o /tmp/curl-impersonate.tar.gz \
        "https://github.com/lwthiker/curl-impersonate/releases/download/v${CURL_VER}/curl-impersonate-v${CURL_VER}.x86_64-linux-gnu.tar.gz" && \
      tar -xzf /tmp/curl-impersonate.tar.gz -C /usr/local/bin && \
      chmod +x /usr/local/bin/curl_chrome* && \
      rm /tmp/curl-impersonate.tar.gz; \
    else \
      echo "curl-impersonate: skipping on $ARCH (no pre-built binary available)"; \
    fi

# Download monolith binary to /usr/local/bin so it is never hidden by a
# user-mounted /data volume.  The entrypoint copies it into the volume on
# first start so monolith_bin() (DATA_DIR/bin/monolith) finds it too.
RUN ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64) ASSET="archiveinator-linux-x86_64" ;; \
      aarch64) ASSET="archiveinator-linux-aarch64" ;; \
      *) echo "Unsupported architecture: $ARCH"; exit 1 ;; \
    esac && \
    curl -fsSL -o /usr/local/bin/monolith \
      "https://github.com/p0rkchop/archiveinator/releases/latest/download/${ASSET}" && \
    chmod +x /usr/local/bin/monolith

# Pre-download adblock blocklists to /opt/archiveinator so they are never
# hidden by a user-mounted /data volume.  The entrypoint copies them into
# the volume on first start.
RUN python3 << 'PYEOF'
import httpx, pathlib
for url, dest in [
    ("https://easylist.to/easylist/easylist.txt", "/opt/archiveinator/easylist.txt"),
    ("https://easylist.to/easylist/easyprivacy.txt", "/opt/archiveinator/easyprivacy.txt"),
]:
    pathlib.Path(dest).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(dest).write_bytes(httpx.get(url, follow_redirects=True, timeout=60).content)
print("Blocklists installed to /opt/archiveinator")
PYEOF

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

WORKDIR /data/output
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["serve"]
