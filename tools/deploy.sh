#!/bin/bash
# Hot-deploy to goblin without reflashing. Usage: tools/deploy.sh [inputd|goblin|all]
# Targets are root-owned and the device sudo needs a password (image default),
# so stage in ~ then copy with sudo -S. Remote shell is zsh -> keep commands plain.
# NB: under sudo ~ means /root, so reference the stage dir by absolute path.
set -euo pipefail
cd "$(dirname "$(realpath "$0")")/.."
WHAT="${1:-all}"
PW=rg35xxhh
STAGE=/home/rg/deploy-stage

stage() { ssh goblin "mkdir -p $STAGE"; }
install_as_root() { ssh goblin "echo $PW | sudo -S bash -c '$1'"; }

if [ "$WHAT" = all ] || [ "$WHAT" = inputd ]; then
    python3 src/inputd/tests/test_core.py > /dev/null   # never ship red tests
    stage
    scp -q src/inputd/rg35xxh_inputd/*.py goblin:deploy-stage/
    scp -q overlay/etc/rg35xxh/input.conf goblin:deploy-stage/
    install_as_root "cp $STAGE/*.py /usr/local/lib/rg35xxh-inputd/rg35xxh_inputd/ \
        && cp $STAGE/input.conf /etc/rg35xxh/input.conf \
        && rm -rf $STAGE /usr/local/lib/rg35xxh-inputd/rg35xxh_inputd/__pycache__"
    # bracket keeps pkill from matching its own ssh shell; autostart loop respawns in ~2 s
    # quoted: remote shell is zsh and an unquoted [n] would be a fatal glob
    ssh goblin 'pkill -f "rg35xxh_inputd.daemo[n]" || true'
    echo "inputd deployed (check: ssh goblin tail -5 .local/state/session/inputd.log)"
fi

if [ "$WHAT" = all ] || [ "$WHAT" = goblin ]; then
    stage
    scp -q overlay/usr/local/bin/goblin goblin:deploy-stage/
    install_as_root "cp $STAGE/goblin /usr/local/bin/goblin && chmod 755 /usr/local/bin/goblin && rm -rf $STAGE"
    echo "goblin TUI deployed (takes effect on next launch)"
fi
