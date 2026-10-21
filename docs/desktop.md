# Desktop

## Decision: labwc (Wayland)

A stacking window manager with a traditional taskbar look, plus small separate tools for panel, launcher and power menu, styled to behave like a classic desktop.

### Why labwc over XFCE (X11)

- **Per-output scaling** — the 640×480 handheld screen and a 1080p HDMI display can each have their own scale. X11 has one global scale. Key for the HDMI use case.
- **Lighter** — estimated ~120–200 MB idle vs ~250–350 MB for XFCE on 1 GB RAM.
- **Fuller GPU use** — every frame composited on the GPU (Panfrost); no tearing; video frames can go to the screen without CPU copies.
- Wayland is the current standard; XFCE's Wayland support is incomplete.

Trade-off accepted: more setup work (panel, launcher, power menu, settings assembled from separate tools). Old X11-only apps run through XWayland.

### Why not Sway

Sway (ROCKNIX's default) is a keyboard-driven tiling WM — unsuitable for gamepad/mouse-only use.

## Hardware acceleration

- OpenGL/GLES via Panfrost (Mesa) for the compositor and GL apps (browser rendering, Moonlight).
- **Hardware video decode for Moonlight** (H.264/HEVC, up to 1080p60) via the Cedrus V4L2 stateless decoder — see `video-decode.md`. The system FFmpeg and mpv use the same VPU through the same patchset and have rendered **zero-copy** since 2026-10-17 (`hwdec=auto-safe` selects the `drm` registration of those decoders, whose dmabufs mpv's DRM PRIME interop takes directly): 1080p HEVC and H.264 play with 0 dropped frames over 10 s, 540p with room to spare. Browsers never reach the VPU: Chromium's VA-API route was built and measured (it decodes on Cedrus, then renders green frames), so browser video stays software-decoded — `video-decode.md`.

## Shell components: Waybar + nwg-drawer + wlogout

| Role | Tool | Notes |
|---|---|---|
| Panel | **Waybar** | Bottom taskbar, classic-desktop styling: open windows, clock, battery, network, volume, tray |
| Launcher | **nwg-drawer** | Full-screen app icon grid — usable with mouse/D-pad (type-to-search launchers rejected: no keyboard) |
| Power menu | **wlogout** | Full-screen large buttons: Shut down / Log out / Restart / Sleep. Opened by Power (tap) |
| Notifications | **mako** | |

Chosen over LXQt-on-labwc (heavier) and sfwbar (smaller community) for low RAM and gamepad-friendly large targets.

### Session details (implemented)

- Boot → getty auto-login on tty1 → labwc. Logging out restarts the session; after 3 failed starts a shell is left on tty1. The launcher is `/etc/profile.d/zz-rg35xxh-session.sh`, sourced from `/etc/profile`. Debian's zsh does not read `/etc/profile`, so the overlay ships `/etc/zsh/zprofile` with `emulate sh -c 'source /etc/profile'` — that is what makes the desktop start on the zsh login shell the image now uses (and why switching `rg` to zsh once silently broke it: 2026-10-17, bare tty1 shell after a reboot). Bash login shells are unaffected, so the same image works with either.
- System-wide defaults in `/etc/xdg/` (labwc, waybar, mako, foot, kanshi); per-user overrides go in `~/.config/`.
- Normal windows open **maximized** (640×480 screen); dialogs keep their size.
- Panel: `☰ Apps` (launcher) · open windows · tray · volume · network · battery · clock · `⏻` (power menu).
- Launcher: `rg35xxh-drawer` (4 columns, 56 px icons, no categories/file search). Power menu: `rg35xxh-power-menu`.
- Physical keyboard: Super+D apps, Super+Enter terminal, Super+E files, Super+X power menu, Alt+F4 close, Print screenshot.
- **No xdg-desktop-portal**: it delayed Waybar startup (portal activation timeouts) and is only needed for screen sharing/Flatpak; GTK apps use their own file dialogs.
- Audio: speaker starts at 100 % on a fresh system (`/etc/wireplumber/wireplumber.conf.d/50-rg35xxh.conf`; WirePlumber default is 40 %); the codec DAC and Line Out are set to 100 % by `rg35xxh-hwinit`.
- Memory: zram swap (50 % of RAM, zstd, priority 100) plus a 2 GB swap file `/swapfile` on the SD card (priority 10, created on first boot by `rg35xxh-swapfile`). Chromium flags in `/etc/chromium.d/50-rg35xxh`; uBlock Origin Lite force-installed by policy (`/etc/chromium/policies/managed/ublock-origin-lite.json`, downloaded on first launch).
- Component logs: `~/.local/state/session/*.log`, labwc: `~/.local/state/labwc.log`.

### Shell (zsh)

- The login shell is **zsh** (`/usr/bin/zsh`, from `base.list`). `build/04d-ohmyzsh.sh` installs Oh My Zsh plus `zsh-autosuggestions` and `zsh-syntax-highlighting` into `/etc/skel/.oh-my-zsh` (all pinned to the revisions the handheld runs), `/etc/skel/.zshrc` loads them with a starship prompt (`starship` is in `dev.list`), and `10-image.sh` copies `/etc/skel` into a fresh `/home/rg` — so a reflash keeps the shell environment. `~/.zshrc` is the file to edit for per-user changes (it also adds `~/.opencode/bin` and `~/.local/bin` to `PATH`).
- `overlay/etc/zsh/zprofile` (`emulate sh -c 'source /etc/profile'`) is load-bearing: it is what runs `/etc/profile.d/zz-rg35xxh-session.sh` (desktop) and `dev-tools.sh` (tool `PATH`) for a zsh login shell.
- Oh My Zsh is only a convenience: if `~/.oh-my-zsh` is missing the shell still starts (the `.zshrc` then prints a source error) and the desktop is unaffected.

### External display (mini HDMI) — verified 2026-10-08

- Works with hot-plug: a 1080p monitor came up at 1920×1080 60 Hz, scale 1; taskbar, pointer and windows all fine. No HDMI audio device (only the analog codec appears in ALSA).
- kanshi profiles: `handheld` (DSI-1 only), `docked` (HDMI-A-1 + DSI-1, then runs `rg35xxh-display apply`).
- `rg35xxh-display set monitor|extend|mirror` picks what happens while HDMI is connected; the choice is saved in `~/.config/rg35xxh/display-mode`. Launcher entries: **Display: Monitor only / Extend screens / Mirror screens**.
  - **monitor** (default): handheld screen off (backlight off too). Pressing X turns it on as a full-screen keyboard panel — see `keyboard.md`.
  - **extend**: handheld screen to the right of the monitor.
  - **mirror**: the monitor switches to 640×480 at the same position as the handheld, so both show the same picture (the monitor scales it up).

## Core use

| Need | Decision |
|---|---|
| Remote desktop to PC | **Moonlight** (PC runs Sunshine). Hardware decoding: 1080p60 HEVC smooth on 5 GHz Wi-Fi |
| Parsec | **Not possible** — no Linux ARM64 client |
| External display | mini HDMI, per-output scaling |
| Keyboard/mouse | USB (host port, hub OK) or Bluetooth, alongside the gamepad controls |
| On-screen keyboard | Custom, D-pad navigable, English only (see `input-mapping.md`) |
| CJK text | **Display only** (Noto CJK fonts). No input method |

## App list

Selection rule: light apps for 1 GB RAM; Qt apps preferred where equal, since moonlight-qt already loads Qt.

| Purpose | Package(s) | Why |
|---|---|---|
| Remote desktop | `moonlight-qt` (official Moonlight Cloudsmith repo, debian/trixie arm64) | Core use case |
| Browser | `chromium` + uBlock Origin Lite | Smoothest browser tested on this device (see below). Heavy browsing → use the PC via Moonlight |
| File manager | `thunar` | Light, Wayland-capable, familiar |
| Terminal | `foot` | Lightest Wayland terminal; stable app_id `foot` for copy/paste detection |
| Text editor | `mousepad` (GUI), `micro` + `nano` (terminal) | Simple; micro supports mouse and Ctrl+C/V |
| Python | `python3`, `python3-venv`, `pipx` | System pip is blocked by Debian; use venvs |
| SSH | `openssh-client`, `openssh-server`, `tmux`, `mosh` | SSH server off by default; Apps → **Enable SSH** sets your own password and turns it on. tmux/mosh survive dropped connections |
| Networking | `network-manager`, `network-manager-gnome` (nm-applet) | Wi-Fi from tray; `nmtui` fallback |
| VPN | `tailscale` (official repo pkgs.tailscale.com, debian/trixie) | Reach the device / PC from anywhere; tray icon via `tailscale systray` |
| Bluetooth | `bluez`, `blueman` | |
| Audio | `pipewire`, `wireplumber`, `pipewire-pulse`, `pavucontrol` | |
| Clipboard | `wl-clipboard` | Required by L3/R3 copy/paste |
| Brightness / volume | `brightnessctl`, `wireplumber` (`wpctl`) | Used by F + Vol and Vol keys |
| Screenshots | `grim`, `slurp` | |
| Viewers | `imv` (images), `qpdfview` (PDF), `mpv` (video, VPU decode — see [video-decode.md](video-decode.md)) | |
| Archives | `xarchiver` | |
| System | `htop`, `git`, `zram-tools`, `systemd-timesyncd` | zram = compressed RAM swap |
| Fonts | `fonts-noto-core`, `fonts-noto-cjk`, `fonts-noto-color-emoji` | CJK and emoji rendering |

Locale `en_US.UTF-8`, timezone UTC (change with `sudo timedatectl set-timezone Area/City`).

Heavy web browsing is the expected weak point (1 GB RAM).

### File associations

`/usr/local/share/applications/mpv.desktop` is a full entry — `Exec=mpv -- %U`,
an icon, and the video and audio types it handles — with `NoDisplay=true`: it
is the handler for those types and stays out of the drawer.

Two caches decide whether GIO knows that:

- `/usr/share/mime/mime.cache` (shared-mime-info) holds the content types,
- `/usr/local/share/applications/mimeinfo.cache` (desktop-file-utils) holds
  which application handles which type.

Without them GIO can still guess the type of a file but cannot map it to an
application, so Thunar has no handler and falls back to running a literal `%U`
("missing exec"). The image build refreshes both (`build/05-configure-base.sh`);
an in-place update of the overlay has to do the same.

## Tailscale (added 2026-10-09)

- Installed from Tailscale's official Debian repository; `tailscaled` runs at boot (kernel TUN + WireGuard available, so normal kernel mode, not userspace networking).
- `rg35xxh-tailscale-operator.service` makes the desktop user Tailscale **operator** (`tailscale set --operator=<user>`), so the tray and `tailscale up/down` work without sudo.
- **Log in:** Apps → **Tailscale login** (`rg35xxh-tailscale-login`) opens a terminal with `tailscale up --qr`: scan the QR code with a phone (or open the link) and approve. Login persists across reboots; nothing secret is stored on the boot partition.
- **Tray:** `tailscale systray` is started from the labwc autostart (grey when logged out).
- Defaults: no exit node, routes from other nodes not accepted, MagicDNS on (`/etc/resolv.conf` → 100.100.100.100 while connected).

## Browser choice (v0.1.3)

Tested 2026-10-17 on the device: fresh profile per browser, 20 s of scrolling on Wikipedia and on naver.com (ad-heavy), scored 1–5 by hand, CPU and free memory measured during the scroll.

| Browser | Score (wiki / naver) | CPU | Free RAM |
|---|---|---|---|
| Firefox ESR 153 + uBlock Origin (until v0.1.2) | 2 / 1 | 88 % / 90 % | ~210 MB |
| Firefox + uBlock Origin Lite | 2.5 / 1.5 | 83 % / 77 % | 196–308 MB |
| Firefox, no ad blocker | 2.9 / 2 | 64 % / 69 % | 232–300 MB |
| Epiphany (WebKitGTK) | 2.7 / 2.7 | 39 % / 60 % | 324–456 MB |
| Chromium 155, no ad blocker | 3.5 / 3 | 43 % / 37 % | 374–463 MB |
| **Chromium 155 + uBlock Origin Lite** | **4 / 3** | **38 % / 40 %** | **379–434 MB** |

Earlier rounds showed Firefox's rendering path (GPU/CPU WebRender, Wayland/X11), CPU governor, smooth scrolling and frame rate made no noticeable difference; full uBlock Origin alone took 110–270 MB in Firefox's extension process.


## Goblin (the Jellyfin client, v0.2.0)

`goblin` is the one media app on the handheld: a single Jellyfin client,
keypad-first, no menu/dashboard/launcher modes. `Super+p` (or `Super+m`)
starts it in a terminal. Everything the old suite did (menu, dashboard, play
browser, shuffle) is gone — the client is the whole UI.

* **Pagination**: 50 rows per page, and the next page is fetched when the
  cursor gets within five rows of the end, so a 533-item library paints in
  about a second instead of three (measured on the device: 50 rows = 1.2 s
  end to end — 0.3 s API, 0.6 s mount, 0.25 s paint — against 3.2 s for 200
  rows). The `… N more` row shows how much is left and can be selected to
  pull the next page in.
* **No placeholder rows**: a list row renders its own text. A row built as a
  container (a `Label` inside a `ListItem`) shows the *class name* — "Row" —
  until the child mounts, which is what the big libraries used to flash.
* **Layout**: the full 80x24 terminal goes to the list. One line per row
  (`▶ S01E03 Name  24m  540p  ✓`), a one-line top bar
  (`Home › Film` + `43G free  bat 71%  cpu 23%  33°C`) and a one-line key
  legend at the bottom. No borders, no panels, no wasted rows.
* **Keys** (keypad mode: A=Enter, B=Esc, X=Tab, Y=Space): `A` opens a folder
  or plays from the cursor down the visible list, `B` goes back (clearing the
  search filter first), `Y` saves, `X` deletes the saved copy (twice), `/`
  searches, `Q` quits. Physical keyboard works the same.
* **Icon**: `app-goblin.png` (56 px pixel art — the handheld with a play
  triangle on its screen, drawn by `tools/icons/gen_app_icons.py`, with a
  `-light` variant the theme script swaps in), shown in the app drawer as
  "Goblin".
* **Video**: mpv takes over with `--fullscreen`, so the film fills the
  640x480 panel; the client is gone while it plays, so the keyboard belongs
  to mpv. `B` (Esc) closes the video and the client comes back on the same
  folder and row (mpv's own Esc binding is "cycle pause", so
  `/etc/mpv/input-handtop.conf` rebinds it to `quit` for the client; the
  built-in bindings stay in place).
* **Transcoding**: playing and saving ask Jellyfin for
  `stream.mp4?static=false&videoCodec=h264&audioCodec=aac&maxWidth=640&
  maxHeight=480&videoBitrate=1228800&audioBitrate=96000`. `static=false` is
  the part that matters — without it the endpoint serves the original file and
  every other parameter is decoration. The size is the panel: the server keeps
  the aspect ratio, so 16:9 comes back as 640x360 h264 — a quarter of the
  pixels of 720p, a quarter of the bitrate, and still a picture the 640x480
  screen shows pixel for pixel. `GOBLIN_MAX_WIDTH`/`GOBLIN_MAX_HEIGHT` raise
  it for the HDMI monitor (1280x720 for a 4 Mbit/s stream).
* **Coming back where you were**: the cursor is remembered per folder, and so
  are the pages it needs — after a download or after a video, the list comes
  back with the same rows loaded and the same row under the cursor (the
  rebuilt list is scrolled to it; a resize re-cuts the rows instead of
  rebuilding them, which would throw the cursor away).
* **Resume**: the client reads the stored position of every item
  (`/Users/{id}/Items/Resume`) and shows it on the row as `»55:01`; playing
  starts there (`--start`, per file). Positions the server does not know —
  because an API key creates an *anonymous* session, which Jellyfin refuses
  to store a position for — are tracked by the client itself over mpv's IPC
  socket and shown the same way. The progress is also posted back to
  `/Sessions/Playing/Progress` every 10 s, so a real user token would make
  the web UI show it too.
* **Intro skipping**: the server's media segments (`/MediaSegments/{id}`) are
  honoured — an intro or recap in the first minutes is skipped over
  automatically while the video plays (`GOBLIN_SKIP_INTRO=0` turns it off).
  This server has no segment detection installed, so it is a no-op here.
* **Why the copy decode path**: mpv is started with `--hwdec=drm-copy`.
  Panfrost can only import zero-copy dmabufs whose width is a multiple of 64
  pixels (`MESA: panfrost: rejecting image due to unsupported offset or
  stride alignment`); anything else renders as a flat blue rectangle. 416-wide
  and odd-aspect transcodes hit it constantly. The copy path shows every
  frame — 0 dropped frames at 720p, where the screen is 640x480 anyway.
* **Subtitles**: the client follows the **user's Jellyfin preferences**
  (`GET /Users/{id}` → `Configuration.SubtitleLanguagePreference` and
  `SubtitleMode`), so nothing about languages is hardcoded: set
  *Settings → Playback → Subtitles* in the web UI and the handheld follows.
  The pick is: a track in one of the preferred languages (in the order the
  user listed them), else the media's own default track, else the first text
  track; mode `None` means no subtitles at all. `GOBLIN_SUB_LANGUAGES=ita,eng`
  overrides the profile if you want a different order on the device.
  Jellyfin serves any subtitle stream as srt/ass/vtt on the fly
  (`/Videos/{id}/{source}/Subtitles/{index}/Stream.srt`), and the client
  hands it to mpv as a per-file `--sub-file`, so every episode of the
  playlist gets its own subtitles. The row shows the language that will be
  used (`ita`, `eng`, …). A saved copy gets the subtitle as a sidecar next
  to the video (`<name>.srt`), which mpv loads by itself.
* **Save**: `Y` saves the selected episode, or every episode of a season or
  series, under `~/Offline` (never `/tmp`, which is a 128 MB tmpfs). Series
  are expanded server-side; filenames carry `S01E03`. Files already on the
  device are skipped, and `X` removes them again (the server copy is never
  touched). The free space of the card is on the top bar.
* **Search**: server-side (`SearchTerm`), debounced 400 ms, so a library with
  hundreds of items is searchable. `B` clears the filter before leaving the
  folder.
* **Resume**: the client remembers the folder path, cursor row and filter, so
  quitting a video drops you back on the same row of the same library.
* **A user token for the client**: the config wants a *user* access token,
  not an API key — an API key creates an anonymous Jellyfin session, and the
  server refuses to store a playback position for it. A user token can be
  minted without knowing the password, with the server's QuickConnect flow:

  ```sh
  K=<api key>                       # any admin key
  B=http://server:8096
  UID=$(curl -s -H "Authorization: MediaBrowser Token=\"$K\"" "$B/Users" | python3 -c 'import json,sys;print(json.load(sys.stdin)[0]["Id"])')
  CODE=$(curl -s -X POST -H "Authorization: MediaBrowser Token=\"$K\"" -H 'Content-Type: application/json' -d '{}' "$B/QuickConnect/Initiate" | python3 -c 'import json,sys;print(json.load(sys.stdin)["Code"])')
  curl -s -X POST -H "Authorization: MediaBrowser Token=\"$K\"" "$B/QuickConnect/Authorize?code=$CODE&userId=$UID"
  SECRET=$(curl -s -X POST -H "Authorization: MediaBrowser Token=\"$K\"" -H 'Content-Type: application/json' -d '{}' "$B/QuickConnect/Initiate" | python3 -c 'import json,sys;print(json.load(sys.stdin)["Secret"])')
  curl -s -X POST -H 'Content-Type: application/json' -d "{\"Secret\":\"$SECRET\"}" "$B/Users/AuthenticateWithQuickConnect"
  ```

  The last call returns `AccessToken` — put it in `/etc/default/goblin-dash`
  as `DASH_API_KEY`. With it the server logs the session as the user
  ("User admin started playback"), stores the position, and the web UI shows
  the handheld's progress. Without a user token the client still tracks the
  position itself and shows it as `»55:01`.
* **Headless test** (no device needed, runs against any Jellyfin):
  `python3 tools/test-goblin-tui.py` with `JELLYFIN_URL`/`JELLYFIN_KEY` env —
  covers the library list, the status line, movie and episode playlists (with
  the transcode URL asserted), the resume snapshot, series save targets, a
  real save → play-local → delete round-trip, and back navigation. Verified on
  textual 2.1.2 (Debian trixie, what ships).

## Light theme (dual theme)

**Apps → Theme** (or `rg35xxh-theme dark|light`, `rg35xxh-theme --get`): dark (default) or light. The choice is one file, `~/.config/rg35xxh/theme`, read by every themed part; a switch applies live.

| Part | How it follows the theme |
|---|---|
| Waybar | `rg35xxh-themed waybar` (autostart) adds `-s /etc/xdg/waybar/style-light.css` (imports `style.css`, overrides the colours); the Theme app restarts it |
| Taskbar icons | input mode and battery scripts pick the `-light` PNGs |
| Wallpaper | `rg35xxh-themed swaybg`: `#1e2430` / `#dfe4ec` |
| Notifications | `rg35xxh-themed mako`: `/etc/xdg/mako/config` / `config-light` |
| Window title bars | labwc theme `Handtop` (`/usr/share/themes/Handtop/labwc/themerc`). Light: the Theme app links `/usr/share/themes/Handtop-Light/labwc/themerc` as `~/.local/share/themes/Handtop/labwc/themerc` (user themes win) and runs `labwc --reconfigure`. `themerc-override` only keeps the title-bar padding |
| App drawer | `rg35xxh-drawer` copies `/etc/xdg/nwg-drawer/handtop-<theme>.css` into `~/.config/nwg-drawer` (nwg-drawer's `-s` only takes a name there) |
| Handtop app icons | light: per-user copies of their `.desktop` files in `~/.local/share/applications` with the `-light` icon (marked `X-Handtop-Theme=light`, removed again for dark) |
| Power menu | `rg35xxh-power-menu`: `/etc/wlogout/style.css` / `style-light.css` (buttons stay mid-blue: wlogout's icons are light) |
| GTK apps | `gsettings` color-scheme + `gtk-application-prefer-dark-theme` in `~/.config/gtk-3.0/settings.ini`; open apps may need a restart |

Your own `~/.config/waybar/style.css` or `~/.config/mako/config` still wins over both themes.

Not themed yet (stay dark): terminal (foot), volume/brightness bars (wob), on-screen keyboard, External Controller status screen (it already draws from `PALETTES`, so light is new palette entries). Possible later: follow the time of day.
