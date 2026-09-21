#!/usr/bin/env bash
# Local/test single-node replica set. Keep its key outside the application image and Git.
set -euo pipefail

keyfile=/data/configdb/replica-set.key
if [ ! -s "$keyfile" ]; then
    umask 077
    openssl rand -base64 756 > "$keyfile"
fi
chown mongodb:mongodb "$keyfile"
chmod 400 "$keyfile"

exec /usr/local/bin/docker-entrypoint.sh mongod \
    --replSet rs0 \
    --keyFile "$keyfile" \
    --bind_ip_all \
    --port "${MONGO_PORT:-27017}"
