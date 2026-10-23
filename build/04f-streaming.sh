#!/bin/bash
# yt-dlp, so YouTube/Twitch/etc. can be played on the VPU by mpv.
#
# mpv's ytdl_hook shells out to yt-dlp, prefers the H.264 renditions (the only
# codec Cedrus decodes) and muxes YouTube's DASH video+audio streams; the
# overlay wrapper `goblin-watch` pins those choices. Debian's yt-dlp is too old
# for YouTube (2025.04 cannot pass the SABR/JS challenge), so this installs the
# current release with pipx instead. yt-dlp also wants a JavaScript runtime for
# YouTube; nodejs is already in the image and works (`--js-runtimes node` in the
# wrapper), so no extra runtime is installed.
#
# yt-dlp breaks when YouTube changes things: `pipx upgrade --global yt-dlp` on
# the device is the fix, and this script can simply be rerun when building a new
# image.
set -euo pipefail
TOP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$TOP/build/config.sh"
source "$TOP/build/lib/chroot.sh"
trap chroot_umount EXIT

YTDLP_VERSION="${YTDLP_VERSION:-2026.10.21}"   # version verified on the device
chroot_mount
in_chroot "pipx install --global 'yt-dlp==$YTDLP_VERSION'" >/tmp/ytdlp-install.log 2>&1 \
  || { tail -5 /tmp/ytdlp-install.log >&2; die "pipx install yt-dlp failed"; }
in_chroot "command -v yt-dlp" >/dev/null || die "yt-dlp is not on PATH after install"
in_chroot "command -v node" >/dev/null || die "node is missing (yt-dlp needs a JS runtime)"
echo "yt-dlp $(in_chroot 'yt-dlp --version') with node $(in_chroot 'node --version')"
