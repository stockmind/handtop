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
- **Hardware video decode for Moonlight** (H.264/HEVC, up to 1080p60) via the Cedrus V4L2 stateless decoder — see [video-decode.md](video-decode.md). Other players (mpv, browsers) still decode on the CPU.

## Bluetooth without blueman's tray: trade-offs

Since 2026-10-26 blueman's applet and tray no longer run all the time (they took ~55 MB of the
~1 GB; Handtop's own icon + watcher take ~1 MB). What that changes:

- **Pairing is started from the handheld.** blueman's pairing agent (PIN / passkey prompts) runs
  only while Bluetooth Manager is open. Pairing from the handheld's Bluetooth Manager works as
  before; a phone or PC that starts pairing *to* the handheld while the window is closed gets no
  prompt (and may fail). External Controller mode is not affected (it has its own agent).
- **No tray menu.** blueman's right-click menu (quick connect to recent devices, turn Bluetooth
  off, send files) is gone; the same things are in Bluetooth Manager (tap the icon). Already paired
  devices still reconnect by themselves (that is BlueZ / the device, not the applet).
- **No connection pop-ups** ("connected to …") from blueman's applet while the window is closed.
- **No receiving files over Bluetooth (OBEX)** while the window is closed (blueman's transfer
  service lives in the applet). Rarely used on a handheld.
- **Remembering "Bluetooth off" is now Handtop's job.** blueman's applet used to remember the
  on / off choice; bluetoothd alone switches the adapter on at every start (`AutoEnable`, its
  default). `rg35xxh-bluetooth --watch` saves it (`~/.local/state/rg35xxh-bluetooth-power`, not
  during External Controller mode's set-up) and switches Bluetooth off again at log-in, so it is
  briefly on during boot.
- **The icon is a Waybar module, not a tray item**: it sits right after the input-mode icon,
  before Wi-Fi and Tailscale, and has no right-click menu.
- blueman's own tray icon is switched off in the gsettings defaults (`org.blueman.general
  plugin-list`: `!StatusIcon`, plus `!ShowConnected` and `!StatusNotifierItem`, which would load
  it again), so opening Bluetooth Manager does not add a second Bluetooth icon.

## Session start and log out

Auto-login on tty1 starts labwc (`/etc/profile.d/zz-rg35xxh-session.sh`); **Log out** ends labwc, getty logs in again and a fresh session starts. labwc runs `/etc/xdg/labwc/autostart` in its own process group. Wayland clients (Waybar, applets, …) end with labwc, but the helpers that are not (input daemon loop, battery icon animation, Tailscale tray) would outlive it: so each autostart first stops the previous session's process group (its id is kept in `$XDG_RUNTIME_DIR/rg35xxh-autostart.pgid`; `SIGTERM`, then it **waits until the group is gone**, up to 5 s, then `SIGKILL`) and only then starts the new helpers, and resets the failed-start counter that `zz-rg35xxh-session.sh` uses (3 failed starts in a row leave a shell on tty1). Found 2026-10-26: after a log-out the taskbar showed two Tailscale icons and two input daemons were running. The first fix stopped the old group without waiting, and the next log-out froze the whole handheld: the old input daemon died while the new one was taking over the gamepad and vibration motor. The wait, and the input daemon's clean exit and single-instance lock, are what prevent this; see [services/input-daemon.md](services/input-daemon.md#stopping-restarting-one-instance) before changing either.

## Shell components: Waybar + nwg-drawer + wlogout

| Role | Tool | Notes |
|---|---|---|
| Panel | **Waybar** | Bottom taskbar, classic-desktop styling: open windows, clock, battery, tray |
| Launcher | **nwg-drawer** | Full-screen app icon grid — usable with mouse/D-pad (type-to-search launchers rejected: no keyboard) |
| Power menu | **wlogout** | Full-screen large buttons: Sleep, Restart / Log out, Shut down. Opened by Power (tap) |
| Notifications | **mako** | |

Chosen over LXQt-on-labwc (heavier) and sfwbar (smaller community) for low RAM and gamepad-friendly large targets.

### Session details (implemented)

- Boot → getty auto-login on tty1 → labwc. Logging out restarts the session; after 3 failed starts a shell is left on tty1.
- System-wide defaults in `/etc/xdg/` (labwc, waybar, mako, foot, kanshi); per-user overrides go in `~/.config/`.
- Normal windows open **maximized** (640×480 screen); dialogs keep their size.
- Panel: **Apps** (launcher; blue block with a pixel-art 3×3 app grid) · open windows · input-mode icon · Bluetooth icon · tray (Wi-Fi, Tailscale; pixel-art icons from `tools/icons`) · battery · clock · power (red pixel-art power symbol on the bar, opens the power menu). Even gaps: 8 px between status icons, 12 px around the battery / clock text. Volume and brightness show in the pop-up bar ([services/osd.md](services/osd.md)).
- Launcher: `rg35xxh-drawer` (4 columns, 56 px icons, no categories/file search). Power menu: `rg35xxh-power-menu` ([apps/power-menu.md](apps/power-menu.md)). Theme: [apps/theme.md](apps/theme.md).
- Physical keyboard: Super+D apps, Super+Enter terminal, Super+E files, Super+X power menu, Alt+F4 close, Print screenshot.
- **No xdg-desktop-portal**: it delayed Waybar startup (portal activation timeouts) and is only needed for screen sharing/Flatpak; GTK apps use their own file dialogs.
- Audio: speaker starts at 100 % on a fresh system (`/etc/wireplumber/wireplumber.conf.d/50-rg35xxh.conf`; WirePlumber default is 40 %); the codec DAC and Line Out are set to 100 % by `rg35xxh-hwinit`.
- Memory: zram swap only (all of RAM, zstd): paging to the microSD looked like a hang, so the 2 GB `/swapfile` is gone and `earlyoom` kills the browser instead of freezing the device (see the changelog). Chromium flags in `/etc/chromium.d/50-rg35xxh`; uBlock Origin Lite force-installed by policy (`/etc/chromium/policies/managed/ublock-origin-lite.json`, downloaded on first launch).
- Component logs: `~/.local/state/session/*.log`, labwc: `~/.local/state/labwc.log`.

## Core use

| Need | Decision |
|---|---|
| Remote desktop to PC | **Moonlight** (PC runs Sunshine). Hardware decoding: 1080p60 HEVC smooth on 5 GHz Wi-Fi |
| Parsec | **Not possible** — no Linux ARM64 client |
| External display | mini HDMI, per-output scaling, Display app ([apps/display.md](apps/display.md)) |
| Keyboard/mouse | USB (host port, hub OK) or Bluetooth, alongside the gamepad controls |
| On-screen keyboard | Custom, D-pad navigable, English only (see [services/on-screen-keyboard.md](services/on-screen-keyboard.md)) |
| CJK text | **Display only** (Noto CJK fonts). No input method |

## App list

Selection rule: light apps for 1 GB RAM; Qt apps preferred where equal, since moonlight-qt already loads Qt.

| Purpose | Package(s) | Why |
|---|---|---|
| Remote desktop | `moonlight-qt` (official Moonlight Cloudsmith repo, debian/trixie arm64) | Core use case |
| Browser | `chromium` + uBlock Origin Lite | Smoothest browser tested on this device (see below). Heavy browsing → use the PC via Moonlight |
| File manager | `thunar`, `udisks2`, `gvfs`, `exfatprogs`, `dosfstools`, `eject` | Light, Wayland-capable, familiar. Other drives (TF2 card, USB sticks) mount with a tap — see [apps/files.md](apps/files.md) |
| Terminal | `foot` | Lightest Wayland terminal; stable app_id `foot` for copy/paste detection |
| Text editor | `mousepad` (GUI), `micro` + `nano` (terminal) | Simple; micro supports mouse and Ctrl+C/V |
| Python | `python3`, `python3-venv`, `pipx` | System pip is blocked by Debian; use venvs |
| SSH | `openssh-client`, `openssh-server`, `tmux`, `mosh` | SSH server off by default; Apps → **Enable SSH** ([apps/enable-ssh.md](apps/enable-ssh.md)) sets your own password and turns it on. tmux/mosh survive dropped connections |
| Networking | `network-manager`, `network-manager-gnome` (nm-applet) | Wi-Fi from tray; `nmtui` fallback |
| VPN | `tailscale` (official repo pkgs.tailscale.com, debian/trixie) | Reach the device / PC from anywhere; see [apps/tailscale-login.md](apps/tailscale-login.md) |
| Bluetooth | `bluez`, `blueman` | Taskbar icon: `rg35xxh-bluetooth` (Waybar `image#bluetooth`, Handtop pixel icons: off / on / connected; `--watch` follows BlueZ over D-Bus, ~1 MB). Click: Bluetooth Manager (blueman), with blueman's applet (pairing agent) running only while it is open. Replaced blueman's always-running applet + tray (~55 MB) on 2026-10-26; trade-offs below |
| Audio | `pipewire`, `wireplumber`, `pipewire-pulse`, `pavucontrol` | |
| Clipboard | `wl-clipboard` | Required by L3/R3 copy/paste |
| Brightness / volume | `brightnessctl`, `wireplumber` (`wpctl`) | Used by F + Vol and Vol keys; the pop-up bar is Handtop's own `rg35xxh-osd`, see [services/osd.md](services/osd.md) |
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

## Jellyfin (the media client, v0.2.0)

> The full reference — keys, configuration, the feature set, the mocked
> screenshots — is in **[jellyfin.md](jellyfin.md)**. This section is the short
> version.

`jellyfin` is the one media app on the handheld: a single Jellyfin client,
keypad-first, no menu/dashboard/launcher modes. `Super+p`
starts it in a terminal. Everything the old suite did (menu, dashboard, play
browser, shuffle) is gone — the client is the whole UI.

* **Pagination**: 25 rows per page — mounting a row costs the A53 about
  17 ms, so 200 rows would freeze the UI for 3.4 s — and the next page is
  fetched while the cursor is still ten rows away, so the pause happens while
  you read. A page that arrives keeps the view in place, and a download that
  finishes only repaints the rows it changed instead of rebuilding the list. The `… N more` row shows how much is left and can be selected to
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
* **Icon**: `app-jellyfin.png` (56 px pixel art — the jellyfin mark, white on
  a purple tile, drawn by `tools/icons/gen_app_icons.py`, with a `-light`
  variant the theme script swaps in), shown in the app drawer as "Jellyfin".
* **Keypad during playback**: the mpv window has the focus, and
  `/etc/mpv/input-handtop.conf` maps the rest of the pad onto it — D-pad
  left/right seek 15 s, D-pad up/down change the **speed** (0.25x per
  press, `A`/Enter puts it back to 1x; the hardware keys do the volume),
  `Y` (Space) pauses, `X` (Tab) switches the subtitle track, `B` (Esc)
  closes the video and drops back into the library.
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
  screen shows pixel for pixel. `JELLYFIN_MAX_WIDTH`/`JELLYFIN_MAX_HEIGHT` raise
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
  automatically while the video plays (`JELLYFIN_SKIP_INTRO=0` turns it off).
  This server has no segment detection installed, so it is a no-op here.
* **The decode path**: mpv is started with `--hwdec=drm` — zero-copy, the
  decoder's dmabufs go straight to the GPU. Every width works: the Cedrus
  driver gives the picture a 64-byte aligned stride, which is what panfrost
  needs to import it (before 2026-10-22 the stride was 16-byte aligned, so
  panfrost refused anything whose width was not a multiple of 64 and the
  video area stayed a flat blue rectangle — 416-wide and odd-aspect
  transcodes hit it constantly). Measured on the device at 640×360: **16 %
  CPU** with zero-copy against 28 % for the copy path, and 0 dropped frames.
* **Subtitles**: the client follows the **user's Jellyfin preferences**
  (`GET /Users/{id}` → `Configuration.SubtitleLanguagePreference` and
  `SubtitleMode`), so nothing about languages is hardcoded: set
  *Settings → Playback → Subtitles* in the web UI and the handheld follows.
  The pick is: a track in one of the preferred languages (in the order the
  user listed them), else the media's own default track, else the first text
  track; mode `None` means no subtitles at all. `JELLYFIN_SUB_LANGUAGES=ita,eng`
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

  The last call returns `AccessToken` — put it in `/etc/default/jellyfin`
  as `DASH_API_KEY`. With it the server logs the session as the user
  ("User admin started playback"), stores the position, and the web UI shows
  the handheld's progress. Without a user token the client still tracks the
  position itself and shows it as `»55:01`.
* **Headless test** (no device needed, runs against any Jellyfin):
  `python3 tools/test-jellyfin-tui.py` with `JELLYFIN_URL`/`JELLYFIN_KEY` env —
  covers the library list, the status line, movie and episode playlists (with
  the transcode URL asserted), the resume snapshot, series save targets, a
  real save → play-local → delete round-trip, and back navigation. Verified on
  textual 2.1.2 (Debian trixie, what ships).

## Streams (`goblin-tv`)

A keypad-first browser for YouTube and Twitch, with the same feel as `jellyfin`.
It asks first — **Twitch** or **YouTube** — and Esc returns to that question, so
the entry point is one Enter away from live streams or from a search. Twitch
opens on the top live streams (viewers + game), `3` lists the top
categories and Enter opens a category's streams; `1` shows YouTube (a few topic shortcuts, since YouTube has no
cookie-free "featured" list); `4` shows what you played last (kept in
`~/.local/state/goblin-tv/recent.json`). One box does search and filter:
**typing narrows the list on screen** by title/channel/game, and **Enter searches
the current source** — YouTube videos on `1`, Twitch channels on `2`/`3`
(`searchFor(userQuery:)`, live ones first, offline ones marked). `/` (or Tab)
focuses the box, B/Esc clears it without losing the list.
`5` switches playback between 480p and 720p. Focus stays where you put it: the
list takes it after a load so Enter plays, the box keeps it while you type. Enter plays through `goblin-watch`
— mpv on the VPU, H.264 preferred — and the keys while it plays are the same as
in `jellyfin` (`/etc/mpv/input-handtop.conf`): **B/Esc closes the stream and drops
you back into the list you were in**, D-pad left/right seeks 15 s, up/down changes
speed, A resets it, Y pauses, X switches subtitles. mpv keeps off the terminal
(`--terminal=no --input-terminal=no`), so the TUI returns exactly as it was.

Discovery needs no API keys: YouTube goes through yt-dlp's search, Twitch
through its public web GQL endpoint. Rows are read-only text (titles contain
`[`, so no Textual markup). 480p is the default because the panel is 640×480 and it is much cheaper:
measured on the same YouTube video, 480p (854×480) is **29 % of one core and
143 MB**, 720p (1280×720) is **49 % and 146 MB**, with no visible difference at
this size. 720p stays one keypress away. For comparison, the same video in
Chromium is 154–174 % / ~1 GB, software-decoded.
