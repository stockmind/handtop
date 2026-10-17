# Handtop changelog

## Unreleased

- Fix: install `tumbler`. Thunar without the freedesktop thumbnail service crashed its OpenURI path (`exo-open`, trixie exo 4.20) and opening a video failed with a missing-exec error even when mimeapps.list was correct. Fresh homes also get mpv associations now (skel mimeapps.list above); both applied on the live device.

- Fix: fresh homes now ship `~/.config/mimeapps.list` (`overlay/etc/skel/.config`) with mpv as the default for every video type. Thunar had no handler and its launcher fell back to executing a literal `%U` ("missing exec"); double-clicking a video now opens mpv. Applied on the live device too, and `/etc/skel/.config/mimeapps.list` updated there.

- Change: `/etc/mpv/mpv.conf` gained an `[av1]` profile (`hwdec=no`). The Cedrus VPU has no AV1 decoder in this kernel, and `auto-safe` still tries `av1-drm`/`av1-drm-copy` first — both fail on every frame here instead of falling back cleanly. Software (dav1d) plays AV1 real time with 0 dropped frames (measured 2026-10-17: 1920x884@24 and 3840x1772@30 music videos); HEVC/H.264 keep zero-copy `drm`. The profile must come last in the file: activating a profile re-enables options set above it.

- Docs: Chromium's VA-API route to the VPU was built, measured and rejected. It works as far as the decoder — `VaapiVideoDecoder` drives `/dev/video0` (Cedrus), 81 % of one core at 1080p24 against 185–195 % in software, 0 dropped frames once past startup — but the picture never reaches the screen: a solid green rectangle in every configuration, because Chromium's Linux decoder only offers the GL output path and has nothing to fall back on. `docs/video-decode.md` carries the backend build, the measurements and the flag matrix; no image change follows from it, Chromium video stays software-decoded.

- Change: the image ships **zsh as the login shell** with the shell setup the handheld has been running: `zsh` joins `base.list`, `05-configure-base.sh` sets it for `rg`, and `/etc/skel/.zshrc` (Oh My Zsh + `git`/`docker`/`zsh-autosuggestions`/`zsh-syntax-highlighting` + starship) is copied into every fresh home. Oh My Zsh and the two custom plugins come from the new `build/04d-ohmyzsh.sh`, pinned to the revisions the device runs. Until now the environment had to be recreated by hand after a reflash; a reflash now keeps it. The `overlay/etc/zsh/zprofile` hook above is what starts the desktop on a zsh login shell.
- Fix: switching the login shell to zsh left the device on a bare tty1 shell after a reboot (no desktop). The session launcher is `/etc/profile.d/zz-rg35xxh-session.sh` and Debian's zsh does not read `/etc/profile`, so it never ran; the overlay now ships `/etc/zsh/zprofile` with `emulate sh -c 'source /etc/profile'`, which restores `/etc/profile.d` (session launcher, dev-tools PATH) for zsh login shells.

- Fix: hardware video decoding now works in the system ffmpeg and mpv. `build/04c-v4l2-ffmpeg.sh` cross-builds Kwiboo's FFmpeg (`v4l2-request-n7.1.3`, the V4L2 Request API patchset — the same code Moonlight embeds) instead of jc-kynesim/rpi-ffmpeg. The old build registered only the mainline `drm` hwaccel, which segfaults against Cedrus; the new one registers the `v4l2request` hwdevice and the h264/hevc/av1/vp8/vp9/mpeg2video hwaccels. Measured on the device: a full 23:55 540p HEVC episode decoded at 108 fps (4.5× real time) with 0 decode errors, and `mpv --hwdec=v4l2request-copy` reports "Using hardware decoding".
- Fix: zero-copy playback works, and `/etc/mpv/mpv.conf` now ships `hwdec=auto-safe` + `profile=fast`. An FFmpeg-side patch (`build/patches/ffmpeg-v4l2request-drm.patch`, applied by `04c`) registers the stateless V4L2 request decoders under the `drm` hwdevice as well, so stock mpv's DRM PRIME interop renders their dmabufs. Measured on the device: 540p HEVC 0 dropped frames over 10 s (whole 23:55 episode too), and 1080p HEVC/H.264 0 dropped frames once the scaler is bilinear — the default high-quality scaler was the real 1080p bottleneck (23 → 51 fps), not the decoder, which sustains 99 fps (HEVC) and 51 fps (H.264) in zero-copy and roughly half that in copy mode. `auto-safe` still falls back to the copy variants and then to software; that software path is unchanged and still segfaults intermittently inside Mesa's panfrost driver (3/5 runs, with Debian's stock libavcodec), which is why hardware decoding is preferred.
- Fix: images shipped a stale second copy of the patched ffmpeg under `/usr/local` (an earlier revision of `build/04c` used `--prefix=/usr/local`). Because `/usr/local/bin` precedes `/usr/bin` in `PATH`, the `ffmpeg` a user ran was that old build with no `v4l2request`; mpv was unaffected (the loader prefers `/usr/lib`). `04c` now removes it.
- Fix: the desktop user could not open the dma-buf heaps (`/dev/dma_heap/*` are `root:root 0600`), so ffmpeg logged `Unable to open any dma_heap device` and every dmabuf-based hardware path was unavailable. New udev rule `72-rg35xxh-dma-heap.rules` grants group `video` access.
- Docs: rewrote `docs/video-decode.md` with the measurements above; `tools/check-video-decode.sh` now requires a real decode (Cedrus VPU engaged, 0 decode errors, exit 0) instead of a capability listing — that listing is what let the earlier broken build through. The same tool now also asserts the zero-copy path (`mpv --hwdec=auto-safe` selecting the `drm` hwdec and using the drmprime EGL dmabuf interop), and `docs/desktop.md` no longer calls zero-copy a gap.
- Add: `build/patches/mpv-v4l2request-drmprime.patch` + `tools/build-mpv-v4l2request.sh` (route B): ~20 lines in mpv's `vd_lavc.c` that make the original `--hwdec=v4l2request` zero-copy by creating the device that decoder wants when the VO only offers a differently typed interop. Kept as the alternative to the shipped FFmpeg-side route; the image build does not rebuild mpv. The tool builds the package in a throwaway clone of the rootfs so `apt-get build-dep mpv` cannot overwrite the patched FFmpeg libraries.

## v0.1.3

- **Browser: Chromium replaces Firefox.** On-device tests: Chromium with uBlock Origin Lite scrolled smoothest (4/3 vs Firefox's 2/1 on Wikipedia/Naver) at less than half the CPU, with ~200 MB more free RAM. uBlock Origin Lite is installed automatically by policy on first launch (needs internet). Details in `docs/desktop.md`.
- `/tmp` raised from 128 MB to 256 MB (it filled up during heavy browsing, which also broke `apt update`). It only uses RAM when filled.

## v0.1.2

- **DDR3 boards:** RG35XX H units with DDR3 RAM (dead on power-on with the standard image) now have their own image, `…-DDR3.img.xz`; build with `RAM_TYPE=DDR3`. Thanks @Aaronhrndz (#1). Charging while off is not confirmed on DDR3 yet.
- **On-screen keyboard:** typing follows whichever button is bound to `click_left`, so remapped layouts (e.g. B to confirm) work on the keyboard too. Thanks @Aaronhrndz (#2).
- Docs updated for both.

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
