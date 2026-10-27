#!/bin/bash
# Hot-deploy to goblin without reflashing. Usage: tools/deploy.sh [inputd|jellyfin|all]
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
    # /etc/default/jellyfin is device state (the user's Jellyfin key), the repo only has the
    # template, so it is never overwritten. Services are on-demand, units only need a reload.
    stage
    tar -C overlay --exclude=etc/default/jellyfin --owner=0 --group=0 --numeric-owner \
        -czf - . | ssh goblin "cat > $STAGE/overlay.tgz"
    # The desktop entries in the overlay are only registered with GIO when their
    # directory has a mimeinfo.cache; without it a fresh home has no handler for
    # a video file (Thunar runs a literal "%U"). Same two commands the image
    # build runs (build/05-configure-base.sh).
    # rm the leftovers of the 2026-10-28 rename: the client is jellyfin now
    install_as_root "rm -f /usr/local/share/applications/goblin.desktop \
        /usr/local/share/rg35xxh/icons/app-goblin.png /usr/local/share/rg35xxh/icons/app-goblin-light.png \
        /home/rg/.local/share/applications/goblin.desktop /usr/local/bin/goblin \
        && if [ -f /etc/default/goblin-dash ] && [ ! -f /etc/default/jellyfin ]; then \
             mv /etc/default/goblin-dash /etc/default/jellyfin; fi \
        && if [ -d /home/rg/.local/state/goblin ] && [ ! -d /home/rg/.local/state/jellyfin ]; then \
             mv /home/rg/.local/state/goblin /home/rg/.local/state/jellyfin; fi"
    install_as_root "tar -xzf $STAGE/overlay.tgz -C / && rm -rf $STAGE \
        && systemctl daemon-reload && udevadm control --reload-rules \
        && update-mime-database /usr/share/mime \
        && update-desktop-database /usr/local/share/applications \
        && update-desktop-database /usr/share/applications"
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

if [ "$WHAT" = all ] || [ "$WHAT" = jellyfin ]; then
    stage
    scp -q overlay/usr/local/bin/jellyfin goblin:deploy-stage/
    # rm the pre-2026-10-21 leftovers: the old wrapper and the abandoned
    # goblin-play-tui.py (both are in git history if they are ever needed).
    install_as_root "cp $STAGE/jellyfin /usr/local/bin/jellyfin && chmod 755 /usr/local/bin/jellyfin \
        && rm -f /usr/local/bin/goblin-play /usr/local/lib/goblin-play-tui.py \
        && rm -rf $STAGE"
    echo "jellyfin client deployed (takes effect on next launch)"
fi
