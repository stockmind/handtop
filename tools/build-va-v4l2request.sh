#!/bin/bash
# Cross-build sofus13/libva-v4l2_request (tag 1.3) — the VA-API backend driver
# over the V4L2 stateless Request API — inside a qemu chroot of the image
# rootfs, so the .so is ready to push the moment the device is reachable.
# (On-device compile costs ~an hour on 1 GB of RAM; this takes ~a minute.)
#
# Context: docs/video-decode.md ("Watching video with VLC", "Chromium").
# The driver is what lets VA-API clients reach Cedrus. Three fixes on top of tag
# 1.3 (build/patches/libva-v4l2-request-fixes.patch) make VLC 3 and Chromium
# display decoded frames, VLC zero-copy: a working vaAcquireBufferHandle(), one
# plane per exported layer regardless of the hint, and keeping (not dropping) a
# surface backing that a client imported before the first decode.
#
# Tag 1.3 is deliberate. Upstream master (f54d8d2, "surface: simplify backing")
# has the better design - one CAPTURE buffer per surface, queued with
# V4L2_MEMORY_DMABUF, so surface memory is stable from creation - but it
# requires V4L2_CAP_VIDEO_M2M_MPLANE and cedrus advertises only
# V4L2_CAP_VIDEO_M2M, so it fails to initialise here ("no V4L2 Request API
# decoder found"). Revisit if the kernel driver grows multiplane support.
#
# The artifact is staged at work/va-driver/v4l2_request_drv_video.so; --ship
# installs it into the rootfs, and tools/test-va-v4l2request.sh runs the checks
# on the device. Nothing selects the driver unless a client sets
# LIBVA_DRIVER_NAME=v4l2_request, so shipping it changes no default behaviour.
#
# Needs qemu-aarch64 binfmt and root. Run from anywhere:
#
#   sudo tools/build-va-v4l2request.sh [--ship]
#
# --ship additionally installs the driver into $ROOTFS (future images).
set -euo pipefail
TOP="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
source "$TOP/build/config.sh"
source "$TOP/build/lib/chroot.sh"
trap chroot_umount EXIT

VA_TAG="1.3"
VA_URL="https://github.com/sofus13/libva-v4l2_request.git"
SRC="$WORK/src/libva-v4l2_request"
OUT="$WORK/va-driver"
DEV_PKGS="meson ninja-build pkg-config libva-dev libdrm-dev ca-certificates git"

# Fresh pinned checkout on the host side (network here, not in the chroot).
[ -e "$SRC" ] && safe_rm -r "$SRC"
mkdir -p "$SRC"
git init -q "$SRC"
(cd "$SRC" && git remote add origin "$VA_URL" && git fetch -q --depth 1 origin "refs/tags/$VA_TAG" && git checkout -q FETCH_HEAD)
grep -q "v4l2_request" "$SRC/meson.build" || die "unexpected checkout at tag $VA_TAG"

# Interop fixes for mpv-like dmabuf consumers and VLC 3 (docs/video-decode.md,
# "VLC"): vaAcquireBufferHandle() is implemented instead of returning
# UNIMPLEMENTED, and NV12/P010 export one plane per layer even when the client
# passes flags=0 - VLC 3 asks that way but rejects a composite layer.
patch -d "$SRC" -p1 -s --forward < "$TOP/build/patches/libva-v4l2-request-fixes.patch" \
  || die "the driver fixes patch did not apply"
for sym in "buf_info->mem_size = v4l2r_buffer_bytes(buffer)" keep_backing; do
  grep -rq "$sym" "$SRC/src" || die "the driver fixes patch did not apply ($sym)"
done

chroot_mount
in_chroot "apt-get update -qq && apt-get install -y -qq --no-install-recommends $DEV_PKGS"

# Build inside the chroot (arm64 via binfmt). Source goes in without .git.
in_chroot "mkdir -p /opt/va-build"
tar -C "$SRC" --exclude=.git -cf - . | tar -C "$ROOTFS/opt/va-build" -xf -
in_chroot "cd /opt/va-build && meson setup build >/dev/null && ninja -C build"

mkdir -p "$OUT"
cp "$ROOTFS/opt/va-build/build/src/v4l2_request_drv_video.so" "$OUT/"
in_chroot "test -f /opt/va-build/build/src/v4l2_request_drv_video.so"
safe_rm -r "$ROOTFS/opt/va-build"

SO="$OUT/v4l2_request_drv_video.so"
[ -f "$SO" ] || die "driver .so not found under $OUT"
file "$SO" | grep -q "ARM aarch64" || die "driver is not arm64"

if [ "${1:-}" = "--ship" ]; then
  install -m755 "$SO" "$ROOTFS/usr/lib/aarch64-linux-gnu/dri/"
  echo "shipped to $ROOTFS/usr/lib/aarch64-linux-gnu/dri/"
fi
echo "artifact: $SO ($(stat -c%s "$SO") bytes, tag $VA_TAG)"
