# Handtop changelog

## Unreleased

- Fix: switching the login shell to zsh left the device on a bare tty1 shell after a reboot (no desktop). The session launcher is `/etc/profile.d/zz-rg35xxh-session.sh` and Debian's zsh does not read `/etc/profile`, so it never ran; the overlay now ships `/etc/zsh/zprofile` with `emulate sh -c 'source /etc/profile'`, which restores `/etc/profile.d` (session launcher, dev-tools PATH) for zsh login shells.

- Fix: hardware video decoding now works in the system ffmpeg and mpv. `build/04c-v4l2-ffmpeg.sh` cross-builds Kwiboo's FFmpeg (`v4l2-request-n7.1.3`, the V4L2 Request API patchset — the same code Moonlight embeds) instead of jc-kynesim/rpi-ffmpeg. The old build registered only the mainline `drm` hwaccel, which segfaults against Cedrus; the new one registers the `v4l2request` hwdevice and the h264/hevc/av1/vp8/vp9/mpeg2video hwaccels. Measured on the device: a full 23:55 540p HEVC episode decoded at 108 fps (4.5× real time) with 0 decode errors, and `mpv --hwdec=v4l2request-copy` reports "Using hardware decoding".
- Fix: `/etc/mpv/mpv.conf` now defaults to `hwdec=v4l2request-copy`. Zero-copy `--hwdec=v4l2request` cannot be used (mpv has no render-API interop for the `v4l2request` hwdevice, and `vo=dmabuf-wayland` refuses its frames), and software decoding segfaults intermittently inside Mesa's panfrost driver on this device — 3/5 normal-playback runs, 5/5 with `vo=gpu-next`, reproduced with Debian's stock libavcodec, so it predates this change — while 25/25 hardware-copy runs were clean. The copy variant costs throughput (~45 fps at 540p, ~15 fps at 1080p), so 1080p plays below real time; Moonlight's own zero-copy FFmpeg is unaffected.
- Fix: images shipped a stale second copy of the patched ffmpeg under `/usr/local` (an earlier revision of `build/04c` used `--prefix=/usr/local`). Because `/usr/local/bin` precedes `/usr/bin` in `PATH`, the `ffmpeg` a user ran was that old build with no `v4l2request`; mpv was unaffected (the loader prefers `/usr/lib`). `04c` now removes it.
- Fix: the desktop user could not open the dma-buf heaps (`/dev/dma_heap/*` are `root:root 0600`), so ffmpeg logged `Unable to open any dma_heap device` and every dmabuf-based hardware path was unavailable. New udev rule `72-rg35xxh-dma-heap.rules` grants group `video` access.
- Docs: rewrote `docs/video-decode.md` with the measurements above; `tools/check-video-decode.sh` now requires a real decode (Cedrus VPU engaged, 0 decode errors, exit 0) instead of a capability listing — that listing is what let the earlier broken build through.

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
