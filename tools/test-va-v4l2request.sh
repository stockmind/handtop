#!/bin/bash
# Run the VA-API/Cedrus revisit plan on the goblin device (docs/video-decode.md,
# "Revisit plan"). Assumes tools/build-va-v4l2request.sh produced
# work/va-driver/v4l2_request_drv_video.so.
#
#   tools/test-va-v4l2request.sh push        # stage + install driver, install vainfo
#   tools/test-va-v4l2request.sh info        # vainfo gate: expect H264/HEVC VLD profiles
#   tools/test-va-v4l2request.sh chromium    # screenshot matrix: GL baseline,
#                                            #   --disable-gpu-compositing, --use-angle=vulkan
#   tools/test-va-v4l2request.sh firefox     # firefox-esr (driver's documented client);
#                                            #   needs RDD sandbox off, ~5 min cold start on 1 GB
#
# Screenshots land in work/va-shots/ here; green rectangle = the known failure,
# real picture = win. Chromium must NOT be running already (script kills it).
set -euo pipefail
TOP="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.." && pwd)"
SO="$TOP/work/va-driver/v4l2_request_drv_video.so"
SHOTS="$TOP/work/va-shots"
G="ssh goblin"
WENV="export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0"

[ -f "$SO" ] || { echo "missing artifact; run: sudo tools/build-va-v4l2request.sh"; exit 1; }
mkdir -p "$SHOTS"

case "${1:-}" in
push)
  scp -q "$SO" goblin:~/
  $G "sudo -S true <<< rg35xxhh"   # warm the sudo timestamp
  $G 'bash -s' <<'EOF'
set -e
echo rg35xxhh | sudo -S sh -c '
  install -m755 /home/rg/v4l2_request_drv_video.so /usr/lib/aarch64-linux-gnu/dri/
  command -v vainfo >/dev/null || { apt-get update -qq && apt-get install -y -qq vainfo; }
  ldconfig'
echo "installed:"; ls -la /usr/lib/aarch64-linux-gnu/dri/v4l2_request_drv_video.so
EOF
  ;;
info)
  $G "$WENV; LIBVA_DRIVER_NAME=v4l2_request vainfo --display drm --device /dev/dri/renderD128" \
    | grep -E "VAProfile(H264|HEVC)|entrypoints|Driver" || { echo "NO PROFILES — driver not engaging"; exit 1; }
  ;;
chromium)
  # Each variant: play the 1080p H.264 file fullscreen, wait, grim, kill.
  $G "sudo -S true <<< rg35xxhh"
  for variant in baseline no-gpu-composite angle-vulkan; do
    case "$variant" in
      baseline)           flags="" ;;
      no-gpu-composite)   flags="--disable-gpu-compositing" ;;
      angle-vulkan)       flags="--use-angle=vulkan" ;;
    esac
    echo "== $variant ($flags)"
    $G "bash -s" <<EOF
set -e
$WENV
pkill -f chromium || true; sleep 1
LIBVA_DRIVER_NAME=v4l2_request setsid chromium --no-default-browser-check \
  --ozone-platform=wayland \$flags "file://\$(find \$HOME/Downloads/media -iname '*1080*' \( -iname '*.mp4' -o -iname '*.mkv' \) | head -1)" \
  >/tmp/chrome-$variant.log 2>&1 &
sleep 25
grim "\$HOME/va-shot-$variant.png" 2>/dev/null || echo "grim failed (is labwc up?)"
pkill -f chromium || true; sleep 2
grep -o "decoding [a-z0-9]* via /dev/video[0-9]* \[[a-z]*\]" /tmp/chrome-$variant.log | head -1 || echo "no VA decode line -> software"
EOF
    scp -q "goblin:$SHOTS-$variant.png" "$SHOTS/" 2>/dev/null || true
    echo "  screenshot: $SHOTS/$variant.png"
  done
  ;;
firefox)
  $G "bash -s" <<EOF
set -e
$WENV
command -v firefox_esr >/dev/null || command -v firefox-esr >/dev/null || { echo 'firefox-esr not installed: sudo apt-get install -y firefox-esr'; exit 1; }
LIBVA_DRIVER_NAME=v4l2_request MOZ_DISABLE_RDD_SANDBOX=1 setsid firefox-esr --new-window "file://\$(find \$HOME/Downloads/media -iname '*1080*' \( -iname '*.mp4' -o -iname '*.mkv' \) | head -1)" >/tmp/firefox-va.log 2>&1 &
echo 'cold start on 1 GB takes minutes; re-run "info"/grim when the window appears'
EOF
  ;;
*)
  sed -n '2,15p' "$0"; exit 1 ;;
esac
