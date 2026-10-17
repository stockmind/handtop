#!/bin/bash
# Build Debian's mpv with build/patches/mpv-v4l2request-drmprime.patch — route B
# of docs/video-decode.md.
#
# The patch is ~20 lines in video/decode/vd_lavc.c. mpv cannot render a
# stateless V4L2-request decoder zero-copy out of the box because that decoder's
# hwdevice is AV_HWDEVICE_TYPE_V4L2REQUEST while the only interop this device has
# (DRM PRIME, used by both vo=gpu and vo=dmabuf-wayland) declares
# AV_HWDEVICE_TYPE_DRM; mpv then silently falls back to software. The patch makes
# mpv create the device the decoder asks for whenever the VO already provides an
# interop for the frames' pixel format, so `--hwdec=v4l2request` renders
# zero-copy.
#
# The image itself ships route A instead — an FFmpeg-side patch
# (build/patches/ffmpeg-v4l2request-drm.patch, applied by
# build/04c-v4l2-ffmpeg.sh) that registers the same decoders under the `drm`
# device type, which stock mpv renders as-is. This script exists for the
# `v4l2request` spelling of the zero-copy path and for testing; the image build
# does not use it.
#
# It builds inside a throwaway clone of the image rootfs, because `apt-get
# build-dep mpv` pulls Debian's libavcodec61 and would overwrite the patched
# FFmpeg libraries in the real rootfs. Needs qemu-aarch64 binfmt, root and about
# three minutes. Run from the repo root:
#
#   tools/build-mpv-v4l2request.sh [--keep]
#
# Artifacts land in work/mpv/ (the .deb, plus work/mpv/extract/usr/bin/mpv).
set -euo pipefail

TOP=$(cd "$(dirname "$0")/.." && pwd)
cd "$TOP"
source build/config.sh
source build/lib/chroot.sh

KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

PATCH="$TOP/build/patches/mpv-v4l2request-drmprime.patch"
[ -f "$PATCH" ] || die "missing $PATCH"
[ -d "$TOP/work/rootfs/usr/bin" ] || die "work/rootfs is not built yet (run the build/0* scripts first)"

CLONE="$TOP/work/mpvbuild"
echo "=== $(date -Is) clone rootfs -> $CLONE"
if [ -e "$CLONE" ]; then
  umount -R "$CLONE" 2>/dev/null || true
  safe_rm -r "$CLONE"
fi
cp -a --reflink=auto "$TOP/work/rootfs" "$CLONE"
ROOTFS="$CLONE"
export ROOTFS

chroot_mount
trap 'chroot_umount' EXIT

install -m 644 "$PATCH" "$ROOTFS/root/$(basename "$PATCH")"
cat > "$ROOTFS/root/mpv-build-inner.sh" <<'INNER'
#!/bin/bash
# Runs inside the cloned rootfs (qemu-aarch64): fetch Debian's mpv source,
# apply the patch, build the package.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "== $(date -Is) build dependencies"
echo "deb-src http://deb.debian.org/debian trixie main" > /etc/apt/sources.list.d/zz-mpvbuild-src.list
apt-get update -qq > /root/mpv-apt.log 2>&1
apt-get install -y --no-install-recommends dpkg-dev build-essential >> /root/mpv-apt.log 2>&1
apt-get build-dep -y mpv >> /root/mpv-apt.log 2>&1

echo "== $(date -Is) source"
mkdir -p /root/mpvsrc
cd /root/mpvsrc
apt-get source mpv >> /root/mpv-apt.log 2>&1
src=$(ls -d /root/mpvsrc/mpv-*/ | head -1)
[ -n "$src" ] || { echo "no mpv source directory" >&2; exit 1; }
cd "$src"

echo "== $(date -Is) apply $(basename /root/mpv-v4l2request-drmprime.patch)"
patch -p1 --dry-run < /root/mpv-v4l2request-drmprime.patch
patch -p1 < /root/mpv-v4l2request-drmprime.patch

echo "== $(date -Is) dpkg-buildpackage (the long part)"
DEB_BUILD_OPTIONS="nocheck parallel=$(nproc)" dpkg-buildpackage -us -uc -b -j"$(nproc)" -tc > /root/mpv-dpkg.log 2>&1
tail -3 /root/mpv-dpkg.log
ls -la /root/mpvsrc/*.deb
echo "== $(date -Is) inner build done"
INNER
chmod 755 "$ROOTFS/root/mpv-build-inner.sh"

in_chroot "bash /root/mpv-build-inner.sh"

echo "=== $(date -Is) collect artifacts"
mkdir -p "$TOP/work/mpv"
cp "$ROOTFS/root/mpvsrc/"*.deb "$TOP/work/mpv/"
deb=$(ls "$TOP/work/mpv/mpv_"*.deb | head -1)
rm -rf "$TOP/work/mpv/extract"
mkdir -p "$TOP/work/mpv/extract"
dpkg-deb -x "$deb" "$TOP/work/mpv/extract"
ls -la "$TOP/work/mpv/extract/usr/bin/mpv"

if [ "$KEEP" = 1 ]; then
  echo "=== clone kept at $CLONE (umount -R $CLONE; rm -rf)"
else
  chroot_umount
  trap - EXIT
  echo "=== $(date -Is) drop the clone"
  safe_rm -r "$CLONE"
fi

echo "=== $(date -Is) done"
cat <<EOF

Patched mpv: $TOP/work/mpv/extract/usr/bin/mpv
Install on a running device (keep the stock binary around first):

  sudo cp /usr/bin/mpv /usr/bin/mpv.stock
  sudo install -m 755 $TOP/work/mpv/extract/usr/bin/mpv /usr/bin/mpv

Only the binary is replaced; it links the Debian libmpv2 the device already has.
On the device, 'mpv --hwdec=help' then lists v4l2request without -copy, and
'mpv --hwdec=v4l2request --vo=gpu -v' logs the drmprime interop.
EOF
