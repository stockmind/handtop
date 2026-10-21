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

if [ "$WHAT" = all ] || [ "$WHAT" = console ]; then
    # Everything else the image would install: scripts, icons, themes, units, rules, configs.
    # /etc/default/goblin-dash is device state (the user's Jellyfin key), the repo only has the
    # template, so it is never overwritten. Services are on-demand, units only need a reload.
    stage
    tar -C overlay --exclude=etc/default/goblin-dash --owner=0 --group=0 --numeric-owner \
        -czf - . | ssh goblin "cat > $STAGE/overlay.tgz"
    install_as_root "tar -xzf $STAGE/overlay.tgz -C / && rm -rf $STAGE \
        && systemctl daemon-reload && udevadm control --reload-rules"
    echo "overlay deployed (scripts, icons, themes, units, rules)"
fi

if [ "$WHAT" = all ] || [ "$WHAT" = session ]; then
    # Running desktop bits pick the new files up: Waybar/mako/swaybg (theme), inputd (respawned
    # by the session autostart loop in ~2 s), labwc config. rg35xxh-themed execs the component,
    # so kill the old one first and detach the new one (setsid), or ssh would hang on it.
    ssh goblin 'bash -c "export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0
        pkill -f \"rg35xxh_inputd.daemo[n]\" || true
        pkill -x waybar || true; sleep 0.3
        setsid rg35xxh-themed waybar >/dev/null 2>&1 &
        pkill -x mako || true; sleep 0.2
        setsid rg35xxh-themed mako >/dev/null 2>&1 &
        pkill -x swaybg || true
        setsid rg35xxh-themed swaybg >/dev/null 2>&1 &
        labwc --reconfigure >/dev/null 2>&1 || true"'
    echo "session restarted (waybar/mako/swaybg/inputd/labwc)"
fi

if [ "$WHAT" = all ] || [ "$WHAT" = goblin ]; then
    stage
    scp -q overlay/usr/local/bin/goblin goblin:deploy-stage/
    install_as_root "cp $STAGE/goblin /usr/local/bin/goblin && chmod 755 /usr/local/bin/goblin && rm -rf $STAGE"
    echo "goblin TUI deployed (takes effect on next launch)"
fi
