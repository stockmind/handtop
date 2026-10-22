# Handtop changelog

## Unreleased

- Fix: the blue video is gone — zero-copy works for every picture width.
  The VPU decodes into a picture whose stride the Cedrus driver aligned to 16
  bytes, and Mali (this SoC has a Mali-G31) only imports linear surfaces
  whose stride and plane offsets are 64-byte aligned. Panfrost refused
  every picture whose width was not a multiple of 64 ("rejecting image due
  to unsupported offset or stride alignment"), the VO kept its clear colour
  and the video area stayed a flat blue rectangle — 416-wide and odd-aspect
  transcodes hit it constantly. The VPU's framebuffer line stride is
  programmable, so `build/kernel/0002-cedrus-64-byte-stride.patch` aligns
  the capture stride to 64 bytes and programs the register from the
  negotiated `bytesperline`. Measured on the device with the patched
  module: 416, 544, 720, 854 and 1366 wide all import without a single
  Mesa rejection, and the zero-copy picture matches the software-decoded
  frame (88 dB PSNR, the difference being the OSD clock).

- Change: the client always plays zero-copy. It used to predict the width
  of every file, start mpv on the copy path for the widths it could not
  predict, and check the width of the frame that was really playing over
  mpv's IPC socket to switch over if the prediction was wrong. With the
  driver's stride fixed none of that is needed: every file is started with
  `--hwdec=drm`.

- Change: `tumbler` is dropped again. It was installed to work around Thunar's "missing exec" error, but that error is the missing MIME database: with the caches refreshed, `exo-open` (what Thunar calls) opens a video with no thumbnail service running at all, and without the caches it fails with tumbler running too. On a 1 GB device the thumbnail service is RAM and CPU for a cosmetic feature, so it goes.


- Fix: file associations work for a fresh home. GIO can guess the type of a file without the MIME databases, but it cannot map a type to an application, so a fresh home had no handler for a video file and Thunar fell back to running a literal `%U` ("missing exec"). The image had no `/usr/share/mime/mime.cache` and no `mimeinfo.cache` for `/usr/local/share/applications` at all; `build/05-configure-base.sh` now refreshes both, and `tools/deploy.sh` does the same when it updates a live device.


- Change: the patched FFmpeg keeps Debian's feature set. The first version of `build/04c-v4l2-ffmpeg.sh` enabled only drm/udev/dav1d, so the replacement was a downgrade against the ~60 external libraries Debian's build uses: no gnutls (no https in libavformat, so mpv could not play URLs), no x264/lame/opus/vorbis/vpx encoders, no libass (no subtitle rendering). The build now enables the same set, installs the runtime side of each into the image, and gates on them (https protocol, the five encoders, the ass filter).

- Change: the replaced FFmpeg libraries are held with `apt-mark` (`libavcodec61`, `libavdevice61`, `libavfilter10`, `libavformat61`, `libavutil59`, `libpostproc58`, `libswresample5`, `libswscale8`), so an upgrade cannot reinstall Debian's ones and silently drop the VPU path. `THIRD-PARTY.md` lists the FFmpeg tree, the pinned commit and the local patch.


- Change: video plays fullscreen and B closes it. The client starts mpv with
  `--fullscreen` (the film fills the 640x480 panel) and the client is out of
  the way while it plays, so the keyboard belongs to mpv: `B` (Esc) closes the
  video and the client returns to the same folder and row. mpv's built-in Esc
  binding is "cycle pause", so `/etc/mpv/input-handtop.conf` rebinds it to
  `quit` for the client.

- Add: resume, progress reporting and intro skipping (the good parts of
  jfsh). The client reads the stored position of every item and shows it on
  the row as `»55:01`; playing starts there, per file. It tracks the position
  itself over mpv's IPC socket (an API key creates an anonymous Jellyfin
  session, which stores nothing) and posts it back to
  `/Sessions/Playing/Progress` every 10 s, so a user token would show it in
  the web UI as well. The server's intro/recap segments are skipped over
  while playing.

- Change: the client transcodes to the panel now, not to 720p: 640x480 (the
  server keeps the aspect ratio, so 16:9 becomes 640x360) at ~1.2 Mbit/s.
  A quarter of the pixels and the bitrate of before, and the picture is
  exactly what the screen can show. `GOBLIN_MAX_WIDTH`/`GOBLIN_MAX_HEIGHT`
  raise it for the HDMI monitor.

- Fix: long lists no longer stutter. A download that finished used to rebuild
  the whole list (every row remounted, the scroll thrown away) while the user
  was scrolling in it; it now only repaints the rows it changed. A page that
  arrives keeps the view where it was, the page size is 25 rows (mounting a
  row costs the A53 ~17 ms) and the next page is fetched while the cursor is
  still ten rows away.

- Change: the subtitle language is no longer hardcoded. The client reads the
  user's Jellyfin preferences (`SubtitleLanguagePreference`, `SubtitleMode`)
  and picks a track accordingly: a preferred language, else the media's
  default track, else the first one; mode `None` means no subtitles. Set it
  in the web UI under Settings > Playback > Subtitles, or override on the
  device with `GOBLIN_SUB_LANGUAGES=ita,eng`.

- Fix: the client picks the decode path per file now: zero-copy (`drm`) when
  the width is 64-pixel aligned — which the panel-sized transcode always is
  (exactly 640 wide) — and the copy path otherwise. Measured on the device at
  640x360: 16 % CPU zero-copy against 28 % for the copy path, 0 dropped
  frames; the old 720p copy stream cost 62 %. The blue frames (panfrost
  rejecting a stride it cannot import) cannot happen on the aligned path.

- Fix: the decode-path rule handles tall sources too. The client now works
  out the width the server will really produce (the source if it fits, exactly
  the cap if the width constraint binds, "unknown" if the height constraint
  binds) instead of assuming the cap: in your library 778 of 782 items play
  zero-copy, and the four square/portrait music videos fall back to the copy
  path, where the width cannot be predicted.

- Add: an icon for the app drawer: `app-goblin.png` (the handheld with a
  play triangle, 56 px pixel art with a `-light` variant), and the drawer
  entry is now "Goblin - Jellyfin client for the handheld" instead of the
  stale "Goblin Menu".

- Fix: the big libraries no longer flash placeholder rows. A list row was a
  `ListItem` with a `Label` inside, and until that child mounted Textual
  renders the widget's class name - so every row showed the literal text
  "Row". Rows render their own text now (also one widget per row instead of
  two).

- Change: the client lists 50 rows per page and fetches the next one when
  the cursor nears the end, instead of pulling 200 rows at once. On the
  device the 533-item music video library paints in ~1.2 s instead of ~3.2 s.

- Change: a second save is queued instead of refused. The downloads wait
  their turn in a queue (the key line shows how many jobs are ahead), so
  several items can be marked for saving in a row.

- Fix: a saved position is actually resumed. Three things were in the way: a
  transcode cannot be seeked into (the server produces one growing file), so
  a resumed item is now streamed from the original with the bitrate capped;
  the client kept its own book of what it watched, because the server does not
  always keep the position a client reports; and the `»27:31` marker was
  pushed off the screen, because the row width counted characters while a CJK
  title takes two cells each.

- Fix: a download no longer blocks the client. It runs detached in a worker
  thread: the list stays usable, the key line shows the progress, and the
  saved marks appear when it is done.

- Fix: every saved file gets its subtitle as a sidecar next to it - not just
  series - so a saved episode, movie or music video is fully offline.

- Fix: the cursor and the pages come back after a download or a video. The
  cursor is remembered per folder, the pages it needs are pulled back in,
  and the rebuilt list is scrolled to it (a resize re-cuts the rows instead
  of rebuilding the list, which threw both the cursor and the scroll away).

- Fix: the blue frame cannot last. The client checks the width of every
  file that plays over mpv's IPC socket and restarts the video on the copy
  path if the width is not 64-pixel aligned after all - the case where
  panfrost cannot import the frame. (The width prediction was wrong for
  exactly the square and portrait music videos, the ones most likely to be
  opened.)

- Add: the keypad controls playback. While a video plays the mpv window has
  the focus, and the D-pad now seeks (left/right) and changes the speed
  (up/down, 0.25x per press; `A` puts it back to 1x - the hardware keys do
  the volume), `Y` pauses and `X` switches the subtitle track - only `B` was
  reachable before.

- Fix: a Jellyfin server that is down now says so ("cannot reach ...") in the
  key line instead of showing an empty list.

- Removed: `goblin-run`, the quick text launcher for applications. The
  icon drawer (nwg-drawer) is the way in; the `Super+r` binding, the script,
  its drawer entry and the `bemenu` package are gone.

- Add: subtitles. The client picks the item's subtitle track (Italian first,
  English second, otherwise whatever text track is there) and hands it to mpv
  per file, so every episode of the playlist is subtitled from the start. The
  row shows the language that will be used. A saved copy keeps its subtitle
  as a sidecar next to the video, and deleting the copy removes it again.

- Change: `goblin` is now one Jellyfin client and nothing else. The menu,
  dashboard, music and app-runner modes are gone, as are the dead
  `goblin-play` wrapper and `goblin-play-tui.py`; the whole 80x24 terminal
  goes to one compact list (one line per item, no borders), with a one-line
  top bar (`Home › Film` + free space, battery, CPU %, temperature) and a
  one-line key legend. Keypad-first: A=play/open, B=back, Y=save, X=delete
  (twice), /=search, Q=quit. `Y` saves a single episode, a whole season or a
  whole series to `~/Offline`; `X` deletes the local copy again.

- Fix: the Jellyfin client streams and downloads **transcoded** media now.
  The old URL (`/Videos/{id}/stream?Container=mp4&VideoCodec=h264&…`) served
  the *original* file — the parameters were decoration — and the resulting
  416-wide stream is one of the shapes that renders blue. The client now asks
  for `stream.mp4?static=false&videoCodec=h264&audioCodec=aac&maxWidth=1280&
  maxHeight=720&videoBitrate=4000000`, which really transcodes (a 1080p HEVC
  source comes back as 1280x720 h264).

- Fix: the blue video. mpv's zero-copy path (`--hwdec=drm`) cannot import
  every dmabuf: panfrost rejects frames whose width is not a multiple of 64
  pixels (`MESA: panfrost: rejecting image due to unsupported offset or stride
  alignment`) and the video area stays a flat blue rectangle — 416-wide and
  odd-aspect transcodes hit it constantly. The client starts mpv with
  `--hwdec=drm-copy` instead (0 dropped frames at 720p); local 1080p files
  keep zero-copy, where the width is 1920 and panfrost accepts it. See
  `docs/video-decode.md`.

- Fix: MPEG-2 and VP8 play on the VPU too. mpv only tries hardware for the codecs on its built-in whitelist, so both stayed on the CPU ("codec mpeg2video is not on whitelist") even though Cedrus decodes them; `/etc/mpv/mpv.conf` now sets `hwdec-codecs=h264,hevc,mpeg2video,vp8` (the option replaces the default list, so H.264/HEVC stay listed). Measured 2026-10-21, 120 frames, `vo=gpu --profile=fast`: MPEG-2 1080i 88.8 -> 45.6 % CPU, VP8 720p 92.1 -> 48.1 %, same fps -- battery and thermal headroom, not frame rate. VP9 and AV1 are deliberately left out of that list: this kernel's Cedrus has no decoder for them and mpv's attempt does not fail cleanly (an error per frame), so they are never attempted and decode in software right away -- which also replaces the `[av1]` profile that only existed to keep mpv from trying them.


- Fix: clicking a video in Thunar works again. `/usr/local/share/applications/mpv.desktop` was a hide-stub from v0.1.0 with no `Exec=`, and it shadows Debian's real entry of the same id, so every association naming `mpv.desktop` failed with "Desktop file didn't specify Exec field" (the stub came back on the device through an overlay deploy). It is now a full entry -- `Exec=mpv -- %U`, an icon, the video and audio types -- and keeps `NoDisplay=true`, so mpv stays out of the drawer and is a usable handler at the same time. No separate `play-mpv.desktop` and no skel `mimeapps.list` are needed: the entry declares the types itself.

- Change: `tools/deploy.sh` grows `console` and `session` targets, so a device can be brought to the image state without a reflash: the whole overlay (scripts, icons, themes, units, rules, mako/waybar/drawer configs) is copied as root with `/etc/default/goblin-dash` left alone, then Waybar/mako/swaybg/inputd/labwc are restarted. `all` runs inputd + console + session + goblin.

- Fix: `tools/check-video-decode.sh` no longer picks a file the hand-held cannot decode. It skipped the first video found even when that was AV1 (no Cedrus AV1 decoder), so the gate reported a broken VPU on a healthy device; it now walks the candidates, skips AV1, and handles filenames with spaces.

- Add: `goblin` (the media TUI) resumes where you were after playback. Quitting mpv reopens the same library folder with the cursor on the same row (and the search filter still applied) instead of dropping back to the library list; a fresh start still lands on the menu.

- Add: the input daemon follows a force-gamepad flag (`$XDG_RUNTIME_DIR/rg35xxh-force-gamepad`, polled every 200 ms): present → gamepad mode, absent → desktop mode. A game launcher (e.g. Halo's) only creates/removes the file, no signal or pid needed, and the handheld is a controller exactly while the game runs, whichever mode it started in. It shares the External Controller app's `request_gamepad`/`request_desktop` path, so held buttons and keypad mode unwind properly. A manual mode change is respected until the flag changes again.

- Change: keypad mode (fork) is folded into upstream v0.2.0's input daemon: it has its own taskbar icon now (generated with `tools/icons`, dark/light/shake), its own `rg35xxh-keys-mode` flag and tooltip, and both external mode requests leave it cleanly (held arrow keys are released, no stray keys in the desktop).

- Add: `goblin-run`, an instant text app launcher built on bemenu (~0.85s to show vs ~5s for the GTK icon drawer, which cold-starts and re-scans every launch). Lists all `.desktop` apps by name; type to filter, Enter launches. Bound to `Super+r`; also added as a desktop entry. bemenu is now in the desktop package list.

- Add: `.desktop` entries for the goblin tools (Dashboard, Play, Menu) so they appear in nwg-drawer under Apps. (The drawer's own 640×480 sizing now comes from upstream v0.2.0: 4 columns, 56px icons, `-spacing 4`.)

- Fix: `goblin-dash` now exports the sourced environment so Jellyfin now-playing actually appears when `/etc/default/goblin-dash` is set.

- Fix: `goblin-dash` now uses the correct Jellyfin 12+ auth header (`Authorization: MediaBrowser Token="…"`) instead of the deprecated query param, enabling live now-playing over the LAN. Added `/etc/default/goblin-dash` as a template for setting `DASH_JELLYFIN` and `DASH_API_KEY`.

- Change: `goblin-dash` gained a quick-links footer (press 1–5 to launch Play/Music/htop/Files/Screen-off from within the dashboard; q quits). Interactive mode now reads stdin in cbreak, so the number keys trigger the tool without waiting for Enter.

- Add: a small daily-use tool suite for the handheld, all dependency-free (sh + python stdlib + fzf): `goblin-dash` (live TUI status dashboard — load/temp/memory/disk/battery/IP/uptime, optional Jellyfin now-playing), `goblin-play` (fuzzy-pick and hardware-decode a video; Jellyfin when `JELLYFIN_URL` is set, else local files), `goblin-music` (audio jukebox), and `goblin` (an fzf launcher tying them together). labwc gains `Super+m` (menu) and `Super+p` (play media). No host/user specifics baked in.

- Fix: AV1 rendered black. This FFmpeg registers `av1` under the drm/v4l2request hw devices, but Cedrus has no AV1 VPU, so the native av1 decoder fails to pick a pixel format and returns zero frames (audio plays, picture is black) — even with `hwdec=no`. The route-A build now configures `--enable-libdav1d` (adds `libdav1d-dev`, gates on `CONFIG_LIBDAV1D` and an installed dav1d decoder), so AV1 decodes in software via dav1d and renders. Rebuilt ffmpeg + image.

- Fix: the real cause of Thunar's "missing exec" error was a stub `/usr/local/share/applications/mpv.desktop` (no `Exec=`) left by an earlier experiment, shadowing the real one in `/usr/share`; GIO resolves `/usr/local` first and reported "Desktop file didn't specify Exec field" for every video. Removed on the device. Added `overlay/usr/local/share/applications/play-mpv.desktop` (a "Play with mpv" Open With entry that bypasses pseudo-gui mode) and `XDG_DATA_DIRS` defaults in `/etc/zsh/zshenv` so login shells never hand GIO an empty data path.

- Fix: install `tumbler`. Thunar without the freedesktop thumbnail service crashed its OpenURI path (`exo-open`, trixie exo 4.20) and opening a video failed with a missing-exec error even when mimeapps.list was correct. Fresh homes also get mpv associations now (skel mimeapps.list above); both applied on the live device. (Superseded: the crash was the missing MIME database, not the missing thumbnailer -- see the MIME fix below -- so `tumbler` is dropped again and Thunar no longer shows thumbnails.)

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
- Removed: the mpv-side alternative (`build/patches/mpv-v4l2request-drmprime.patch` + `tools/build-mpv-v4l2request.sh`, "route B"). It was never shipped: the FFmpeg-side patch covers every consumer (mpv, the `ffmpeg` CLI, anything else a user installs), while an mpv patch would need a distribution package rebuild. The tree keeps the FFmpeg side only.

## v0.2.0

- **BT Controller mode** (requested on Reddit by boldiatti): Apps → External Controller turns the handheld into a Bluetooth LE gamepad ("Handtop Gamepad") for a PC or phone; paired devices reconnect automatically; Select + Start + L1 + R1 stops it (Moonlight's quit combo; a long Start press goes to the other device). Classic-Bluetooth accessories on the handheld pause while it is on. Tested with Windows 11. See `docs/bt-controller.md`.
- **Status screen** while BT Controller mode is on: connection state and the PC's name, a live pixel-art drawing of the handheld's controls, reports/s and signal strength, battery, how to stop.
- **Taskbar battery icon**: 20x11 pixel art with 5 bars (one per 20 %), red bars at 0-20 %, and a charging animation with a lightning bolt (the "+" after the percentage is gone). Also on the BT Controller status screen. Light variants follow the theme.
- **Light theme** (Apps → Theme, or `rg35xxh-theme dark|light`): dark (default) or light, switched live: taskbar and its icons, wallpaper colour, app drawer (with light app icons), power menu, notifications, window title bars and GTK apps. Terminal, volume/brightness bars, on-screen keyboard and the External Controller status screen stay dark for now. New `rg35xxh-themed` starts Waybar/mako/swaybg in the current theme; window decorations moved to a labwc theme, `Handtop` (`/usr/share/themes/Handtop[-Light]`).
- App drawer: the 4th column no longer runs past the right edge of the screen.
- The mouse pointer is hidden in gamepad and BT Controller modes (it comes back when moved in desktop mode).
- **Wired Controller mode** (Apps → External Controller → USB cable): the handheld becomes a wired Xbox 360 controller for a PC (XInput, ~1000 reports/s, game vibration on the handheld's motor, charges meanwhile). Right USB-C port (OTG2/DC) only; one external connection at a time. New kernel module `usb_f_fs_xinput.ko` (build/06c-ffs-xinput.sh).
- External Controller app (was BT Controller): choose Bluetooth or USB cable. New pixel-art app icon; the Theme app's icon is redrawn the same way (both exactly 56 px, the drawer's icon size).
- **Vibration safety:** the handheld's motor driver could freeze the whole system when given never-ending vibration effects (e.g. "infinite" on a web controller tester), forcing a 10 s power-off. The input daemon now only plays timed effects (0.5 s, refreshed every 0.4 s while still wanted), rounds strength to 8 levels and updates the motor at most 10 times a second; game vibration in gamepad mode goes through the same path. Stress-tested at 100 requests/s.
- External Controller app: if the chosen service fails to start, it says so instead of switching modes and opening the status screen.
- BT Controller mode is its own input mode: the controls go only to the other device; apps on the handheld don't see a controller (unlike gamepad mode).
- **Taskbar input-mode icon** (pixel art, 23 px): desktop (mouse), gamepad, BT Controller and Wired Controller (an RG35XX H drawing with coloured X/A/B/Y, plus BT waves or a USB plug). External modes have rainbow-striped glass. On a mode change the old icon shakes like a damped spring before the new one appears, and the handheld vibrates in step with it (`haptic_strength` in the input config; 0 turns the vibration off). Light-taskbar variants: put `light` in `~/.config/rg35xxh/inputmode-icons`. Taskbar height 30 → 32 px so the icon sits exactly centred.
- Notifications now appear above the power menu and fullscreen apps. Fix: mako never read `/etc/xdg/mako/config` (it was started without `-c`), so Handtop's notification style was not applied either; it is now (a `~/.config/mako/config` still takes precedence).
- Input daemon: `SIGUSR2` switches to BT Controller mode (used by the External Controller app).
- Adds `python3-dbus`.

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
