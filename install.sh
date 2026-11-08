#!/usr/bin/env sh
# Pasang Kodo ke Termux / Linux:  sh install.sh
set -e
cd "$(dirname "$0")"
if command -v pkg >/dev/null 2>&1; then
  pkg install -y python git >/dev/null 2>&1 || true
fi
BIN="${PREFIX:-/usr/local}/bin"
mkdir -p "$BIN"
chmod +x bin/kodo
ln -sf "$(pwd)/bin/kodo" "$BIN/kodo"
echo "Kodo terpasang. Coba: kodo run examples/hello.kd"
