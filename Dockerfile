# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

ARG RELEASE_REF=main
ENV XDG_CONFIG_HOME=/config
ENV XDG_DATA_HOME=/data

# Install archiveinator with web extras from GitHub
RUN pip3 install "archiveinator[web] @ git+https://github.com/p0rkchop/archiveinator.git@${RELEASE_REF}"

# Ensure Chromium matches the installed playwright pip package version.
# The base image ships an older playwright/chromium pair; pip may pull a
# newer playwright, so we re-install the matching browser.
RUN python3 -m playwright install chromium

# Download monolith binary from latest GitHub release.
# Install to the path monolith_bin() expects: $XDG_DATA_HOME/archiveinator/bin/monolith
RUN mkdir -p /data/archiveinator/bin /data/archiveinator/output && \
    ARCH=$(uname -m) && \
    case "$ARCH" in \
      x86_64) ASSET="archiveinator-linux-x86_64" ;; \
      aarch64) ASSET="archiveinator-linux-aarch64" ;; \
      *) echo "Unsupported architecture: $ARCH"; exit 1 ;; \
    esac && \
    curl -fsSL -o /data/archiveinator/bin/monolith \
      "https://github.com/p0rkchop/archiveinator/releases/latest/download/${ASSET}" && \
    chmod +x /data/archiveinator/bin/monolith

# Pre-download adblock blocklists
RUN python3 << 'PYEOF'
from archiveinator.blocklist import easylist_path, easyprivacy_path
import httpx
for url, path in [
    ("https://easylist.to/easylist/easylist.txt", easylist_path()),
    ("https://easylist.to/easylist/easyprivacy.txt", easyprivacy_path()),
]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(httpx.get(url, follow_redirects=True, timeout=60).content)
print("Blocklists installed")
PYEOF

WORKDIR /data/output
EXPOSE 8080
ENTRYPOINT ["archiveinator"]
CMD ["serve"]
