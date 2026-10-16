#!/bin/bash
# Install all packages (base + desktop + Moonlight) into the rootfs.
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT
chroot_mount

read_list() { sed 's/#.*//' "$@" | tr -s ' \t\n' ' '; }   # inline comments allowed
PKGS="$(read_list "$TOP/build/packages/base.list" "$TOP/build/packages/desktop.list")"
# Optional dev CLI layer (default off: 1 GB RAM device).
# Enable with BUILD_DEV=1; appends build/packages/dev.list.
if [ "${BUILD_DEV:-0}" = "1" ]; then
  PKGS="$PKGS $(read_list "$TOP/build/packages/dev.list")"
fi

# Moonlight's official repository (Cloudsmith), debian/trixie arm64.
# Recover from an interrupted earlier run.
in_chroot "dpkg --configure -a && apt-get -y -f install"
in_chroot "apt-get update -qq && apt-get install -y -qq --no-install-recommends curl gnupg ca-certificates"
in_chroot "curl -1sLf 'https://dl.cloudsmith.io/public/moonlight-game-streaming/moonlight-qt/gpg.key' \
  | gpg --batch --yes --dearmor -o /usr/share/keyrings/moonlight-qt.gpg"
echo "deb [signed-by=/usr/share/keyrings/moonlight-qt.gpg] https://dl.cloudsmith.io/public/moonlight-game-streaming/moonlight-qt/deb/debian $DEBIAN_SUITE main" \
  > "$ROOTFS/etc/apt/sources.list.d/moonlight-qt.list"
# Tailscale's official repository (stable, debian/trixie).
in_chroot "curl -fsSL https://pkgs.tailscale.com/stable/debian/$DEBIAN_SUITE.noarmor.gpg -o /usr/share/keyrings/tailscale-archive-keyring.gpg"
echo "deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] https://pkgs.tailscale.com/stable/debian $DEBIAN_SUITE main" \
  > "$ROOTFS/etc/apt/sources.list.d/tailscale.list"
in_chroot "apt-get update -qq"

# Report packages that do not exist in the configured repositories before installing.
in_chroot "apt-get install -s --no-install-recommends $PKGS moonlight-qt tailscale > /tmp/apt-sim.txt 2>&1 || true"
MISSING="$(sed -n 's/^E: Unable to locate package //p' "$ROOTFS/tmp/apt-sim.txt" | tr '\n' ' ')"
MISSING="$(echo $MISSING)"
if [ -n "$MISSING" ]; then
  echo "Packages not available:$MISSING" >&2
  echo "$MISSING" > "$WORK/missing-packages.txt"
  exit 1
fi

in_chroot "apt-get upgrade -y"
in_chroot "apt-get install -y --no-install-recommends $PKGS moonlight-qt tailscale"
# Nothing from backports unless we ask for it explicitly.
in_chroot "dpkg -l | awk '/^ii/ && \$3 ~ /bpo/ {print \$2}'" > "$WORK/backports-installed.txt"
if [ -s "$WORK/backports-installed.txt" ]; then
  echo "Packages from backports:"; cat "$WORK/backports-installed.txt"
fi
in_chroot "apt-get clean"
# Dev layer extras (BUILD_DEV=1 images only): shell hooks, docker stays off.
if [ "${BUILD_DEV:-0}" = "1" ]; then
  cp "$TOP/build/dev-tools-profile.sh" "$ROOTFS/etc/profile.d/dev-tools.sh"
  in_chroot "systemctl disable docker.service docker.socket containerd.service" || true
fi
safe_rm -r "$ROOTFS"/var/lib/apt/lists/*
mkdir -p "$ROOTFS/var/lib/apt/lists/partial"
echo "Packages installed. Rootfs size: $(du -shx "$ROOTFS" | cut -f1)"
