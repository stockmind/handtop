#!/bin/bash
# Patched ffmpeg with V4L2 request-API decode (Cedrus VPU) for mpv.
# Debian trixie ships vanilla ffmpeg 7.1; upstream never merged the stateless
# V4L2 decoders, so we cross-compile jc-kynesim/rpi-ffmpeg (7.1 branch, same
# libavcodec ABI) and install to /usr/local, which shadows the system libs.
# mpv then decodes H.264/HEVC/VP8 on the VPU via --hwdec=drm (drmprime).
# VLC/Firefox: no V4L2-request code path exists upstream; not solvable here.
set -euo pipefail
source "$(dirname "$0")/config.sh"
source "$(dirname "$0")/lib/chroot.sh"
trap chroot_umount EXIT

RPI_PIN="6dbf87aefd7f491210abe1e043a1c228fa1439a0"
RPI_URL="https://github.com/jc-kynesim/rpi-ffmpeg"
SRC="$WORK/src/rpi-ffmpeg"
DEV_PKGS="libdrm-dev libudev-dev zlib1g-dev"

chroot_mount
in_chroot "apt-get update -qq && apt-get install -y -qq --no-install-recommends $DEV_PKGS"
chroot_umount

[ -e "$SRC" ] && safe_rm -r "$SRC"
mkdir -p "$SRC"
git init -q "$SRC"
(cd "$SRC" && git remote add origin "$RPI_URL" && git fetch -q --depth 1 origin "$RPI_PIN" && git checkout -q FETCH_HEAD)
[ "$(cd "$SRC" && git rev-parse HEAD)" = "$RPI_PIN" ] || die "rpi-ffmpeg checkout mismatch"

export PKG_CONFIG_SYSROOT_DIR="$ROOTFS"
export PKG_CONFIG_LIBDIR="$ROOTFS/usr/lib/aarch64-linux-gnu/pkgconfig:$ROOTFS/usr/share/pkgconfig"
(cd "$SRC" && ./configure --arch=aarch64 --target-os=linux --enable-cross-compile --cross-prefix=aarch64-linux-gnu- --sysroot="$ROOTFS" --pkg-config=pkg-config --prefix=/usr/local --enable-shared --disable-static --disable-doc --disable-debug --enable-gpl --enable-neon --enable-libdrm --enable-libudev --enable-v4l2-request > "$WORK/ffmpeg-config.log" 2>&1)
(cd "$SRC" && make -j"$(nproc)" > "$WORK/ffmpeg-build.log" 2>&1)
(cd "$SRC" && make DESTDIR="$ROOTFS" install >> "$WORK/ffmpeg-build.log" 2>&1)

file "$ROOTFS/usr/local/bin/ffmpeg" | grep -q "ARM aarch64" || die "ffmpeg is not arm64"

chroot_mount
in_chroot "ldconfig"
in_chroot "ffmpeg -hide_banner -h decoder=hevc" | grep -q "v4l2request" || die "v4l2request hwaccel missing"
in_chroot "ldd /usr/bin/mpv" | grep "libavcodec" | grep -q "/usr/local/lib" || die "mpv misses patched libavcodec"
in_chroot "apt-get purge -y -qq $DEV_PKGS && apt-get autoremove -y -qq --purge && apt-get clean"
safe_rm -r "$ROOTFS"/var/lib/apt/lists/\*
mkdir -p "$ROOTFS/var/lib/apt/lists/partial"
echo "rpi-ffmpeg $RPI_PIN installed to /usr/local."
