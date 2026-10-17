# Handtop changelog

## Unreleased

- Fix: playing an HEVC file with mpv crashed the player. `/etc/mpv/mpv.conf` defaulted to `hwdec=drm`, and the V4L2 request-API path segfaults inside libavcodec's HEVC decoder on this kernel/Cedrus combination. mpv now defaults to software decoding; `docs/video-decode.md` records the measurements and the open lead (the `*_v4l2request` decoders Moonlight links statically).
- Fix: the desktop user could not open the dma-buf heaps (`/dev/dma_heap/*` are `root:root 0600`), so ffmpeg logged `Unable to open any dma_heap device` and every dmabuf-based hardware path was unavailable. New udev rule `72-rg35xxh-dma-heap.rules` grants group `video` access.
- Docs: corrected `docs/video-decode.md` — hardware decoding works for Moonlight only, the VPU hwaccel path does not; added `tools/check-video-decode.sh` to verify the VPU path on a device instead of assuming it from the build.

## v0.1.1

- Fix: Wi-Fi could stop passing traffic while still shown as connected (Realtek rtw88 driver stall with Wi-Fi power save on). Power save is now off during normal use (`/etc/NetworkManager/conf.d/50-rg35xxh-wifi-powersave.conf`); screen-off mode still turns it on and now turns it back off afterwards. Side effect: steadier Wi-Fi latency.
- Build: the Go toolchain download is pinned and SHA-256 checked, for x86_64 and arm64 build hosts.
- README: device photo.

## v0.1.0 — first public release

- ROCKNIX `20261001` hardware layer (kernel 7.2.0) + Debian 13 trixie + labwc desktop
- Input daemon: desktop mode (pointer, clicks, scroll, keys, copy/paste), gamepad mode (Xbox 360 pad), on-screen keyboard, volume/brightness with on-screen bars, power button (menu / 3 s shutdown), stick re-centring
- Moonlight with Cedrus hardware decoding (H.264/HEVC, 1080p60)
- Tailscale with tray icon and QR login
- HDMI hot-plug with monitor-only / extend / mirror modes
- Sleep (s2idle) and auto-sleep; charging while off
- `wifi.txt` import from the boot partition; boot logs on the boot partition
- Firefox ESR with low-RAM settings and uBlock Origin; zram + 2 GB swap file
- SSH off by default; Apps → Enable SSH sets your own password first
