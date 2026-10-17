#!/bin/bash
# Check the hardware video-decode (Cedrus VPU) path on a running Handtop device.
#
# Nothing in the image build can prove this works: the decoders only exist on the
# device, against /dev/video0. Run this there.
#
#   ./check-video-decode.sh [video-file]
#
# With no argument it uses the first HEVC-ish file it finds under ~/Downloads or
# /usr/share; pass any H.264 or HEVC file to be explicit. Exits non-zero if the
# VPU path does not decode.
set -u

FILE="${1:-}"
if [ -z "$FILE" ]; then
  for d in "$HOME/Downloads" /usr/share/mpv /usr/share; do
    [ -d "$d" ] || continue
    FILE=$(find "$d" -maxdepth 3 -type f \( -iname '*.mkv' -o -iname '*.mp4' -o -iname '*.webm' \) 2>/dev/null | head -1)
    [ -n "$FILE" ] && break
  done
fi
[ -n "$FILE" ] && [ -r "$FILE" ] || { echo "usage: $0 <video-file>"; exit 2; }

export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

codec=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$FILE" 2>/dev/null)
echo "file:  $FILE"
echo "codec: ${codec:-unknown}"
fail=0

chk() { # label condition
  if [ "$2" = 0 ]; then printf '  ok    %s\n' "$1"; else printf '  FAIL  %s\n' "$1"; fail=1; fi
}

echo "device:"
[ -e /dev/video0 ] && chk "/dev/video0 present" 0 || chk "/dev/video0 present" 1
lsmod 2>/dev/null | grep -q '^sunxi_cedrus' && chk "sunxi_cedrus loaded" 0 || chk "sunxi_cedrus loaded" 1
if [ -e /dev/dma_heap/system ]; then
  [ -r /dev/dma_heap/system ] && [ -w /dev/dma_heap/system ] \
    && chk "dma-buf heaps readable/writable by $(id -un)" 0 \
    || chk "dma-buf heaps readable/writable by $(id -un) (see 72-rg35xxh-dma-heap.rules)" 1
fi

echo "ffmpeg -hwaccel drm:"
timeout 60 ffmpeg -hide_banner -nostdin -v error -hwaccel drm -t 5 -i "$FILE" -f null /dev/null >/tmp/hwdecfmt.$$ 2>&1
rc=$?
[ $rc -eq 0 ] && chk "decodes without crashing (exit 0)" 0 || chk "decodes without crashing (exit $rc)" 1
grep -q 'Hwaccel V4L2' /tmp/hwdecfmt.$$ && chk "V4L2 request-API hwaccel engaged" 0 \
  || chk "V4L2 request-API hwaccel engaged" 1
sed -n '1,3p' /tmp/hwdecfmt.$$ | sed 's/^/        /'

echo "mpv --hwdec=drm:"
timeout 60 mpv --hwdec=drm --vo=gpu --gpu-context=wayland --no-audio --frames=120 \
      --msg-level=all=info -- "$FILE" >/tmp/hwdecfmv.$$ 2>&1
rc=$?
if grep -qa 'Using hardware decoding' /tmp/hwdecfmv.$$; then
  chk "hardware decoding used (exit $rc)" 0
else
  chk "hardware decoding used (exit $rc, no 'Using hardware decoding' line)" 1
fi
grep -aE 'Using hardware decoding|Using software decoding|VO: \[' /tmp/hwdecfmv.$$ | sed 's/^/        /'

rm -f /tmp/hwdecfmt.$$ /tmp/hwdecfmv.$$
echo
[ $fail -eq 0 ] && echo "RESULT: VPU path OK" || echo "RESULT: VPU path NOT working (see docs/video-decode.md)"
exit $fail
