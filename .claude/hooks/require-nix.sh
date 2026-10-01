#!/bin/sh
# Claude Code runs this at the start of each session, from .claude/settings.json.
# The tools of the book come from Nix through ./dev, so a session needs Nix. A
# cloud container starts without it: there, this installs Nix 2.34.8 for one
# user. On any other machine, it only says that Nix is missing, because the
# owner chooses how to install it (readme.build, "The environment").
set -e
profile=/nix/var/nix/profiles/default/bin
installer=https://releases.nixos.org/nix/nix-2.34.8/install
# The installer holds the hash of each Nix archive, so this hash pins them too.
installer_sha256=96c10e102c88809dd9ec0bee89200c4a51eae4c9f6d8698c26b16788d131e078

if ! command -v nix >/dev/null 2>&1 && [ ! -x "$profile/nix" ]; then
    if [ "${CLAUDE_CODE_REMOTE:-}" != true ]; then
        echo "require-nix: Nix is not installed. Install it from https://nixos.org/download." >&2
        exit 2
    fi
    script=$(mktemp)
    trap 'rm -f "$script"' EXIT
    curl -sSfL --max-time 120 -o "$script" "$installer"
    echo "$installer_sha256  $script" | sha256sum -c --quiet
    # The container runs as root with no nixbld group, so builds run as root.
    mkdir -p /etc/nix
    [ -f /etc/nix/nix.conf ] || echo 'build-users-group =' >/etc/nix/nix.conf
    sh "$script" --no-daemon --no-modify-profile >&2
fi
# Claude Code adds each line of CLAUDE_ENV_FILE to the environment of later commands.
if ! command -v nix >/dev/null 2>&1 && [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    echo "export PATH=$profile:\$PATH" >>"$CLAUDE_ENV_FILE"
fi
