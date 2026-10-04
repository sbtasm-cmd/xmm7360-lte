#!/usr/bin/env bash
# Fetch the RPC helper module from xmm7360-pci, used by the diagnostic tools.
set -euo pipefail
cd "$(dirname "$0")"
tmp=$(mktemp -d)
git clone -q --depth 1 https://github.com/xmm7360/xmm7360-pci.git "$tmp"
rm -rf xmm7360-rpc && cp -r "$tmp/rpc" xmm7360-rpc && rm -rf "$tmp"
echo "xmm7360-rpc ready in $(pwd)/xmm7360-rpc"
