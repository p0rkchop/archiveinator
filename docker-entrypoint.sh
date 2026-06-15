#!/bin/bash
# docker-entrypoint.sh
#
# Bootstraps the /data volume on first start by copying baked assets
# (monolith binary and adblock blocklists) from fixed image paths that
# are never shadowed by a volume mount.  Subsequent starts skip the copy
# because the files already exist.  Then exec the requested command.
set -e

DATA_DIR="${XDG_DATA_HOME:-/data}/archiveinator"
mkdir -p "$DATA_DIR/bin"

# Monolith binary
if [ ! -f "$DATA_DIR/bin/monolith" ]; then
    cp /usr/local/bin/monolith "$DATA_DIR/bin/monolith"
    chmod +x "$DATA_DIR/bin/monolith"
    echo "archiveinator: monolith initialized from image"
fi

# Adblock blocklists
if [ ! -f "$DATA_DIR/easylist.txt" ]; then
    cp /opt/archiveinator/easylist.txt   "$DATA_DIR/easylist.txt"
    cp /opt/archiveinator/easyprivacy.txt "$DATA_DIR/easyprivacy.txt"
    echo "archiveinator: blocklists initialized from image"
fi

exec archiveinator "$@"
