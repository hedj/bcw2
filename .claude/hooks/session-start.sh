#!/bin/bash
# Install Nix in a Claude Code on the web session, so that ./dev make check and
# ./dev make test run in the environment that flake.nix pins.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
    exit 0
fi

# The version of the installer is pinned, so that each session gets the same Nix.
NIX_VERSION=2.35.2
PROFILE=/root/.nix-profile

# The agent proxy of the session re-signs HTTPS, so Nix must trust its CA bundle.
CA_BUNDLE=/root/.ccr/ca-bundle.crt
if [ -f "$CA_BUNDLE" ]; then
    export NIX_SSL_CERT_FILE="$CA_BUNDLE"
fi

if [ ! -x "$PROFILE/bin/nix" ]; then
    mkdir -p /etc/nix
    # The container runs as root with no nixbld users: a single-user install needs no build group.
    {
        echo "build-users-group ="
        if [ -f "$CA_BUNDLE" ]; then echo "ssl-cert-file = $CA_BUNDLE"; fi
    } > /etc/nix/nix.conf
    installer=$(mktemp)
    curl -sSfL -o "$installer" "https://releases.nixos.org/nix/nix-$NIX_VERSION/install"
    sh "$installer" --no-daemon --yes
    rm -f "$installer"
fi

export PATH="$PROFILE/bin:$PATH"
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export PATH=\"$PROFILE/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
    if [ -f "$CA_BUNDLE" ]; then echo "export NIX_SSL_CERT_FILE=\"$CA_BUNDLE\"" >> "$CLAUDE_ENV_FILE"; fi
fi

# Build the environment once here, so that the container cache holds its tools
# and the first ./dev of the session does not download them.
cd "$CLAUDE_PROJECT_DIR"
./dev true
