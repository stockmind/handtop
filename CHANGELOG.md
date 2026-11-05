# Handtop changelog

## Unreleased

- Change: the fork is synced to upstream v0.3.8. Upstream now carries the
  work this fork started (VA-API/Chromium/VLC on the VPU, the cedrus VP9
  series with the reference-stride and padding fixes) and improves it (VP9
  10-bit layout, 10-bit HEVC, Battery saver, low-battery shutdown). The fork
  keeps its own additions: the Jellyfin client and Streams, zram-only memory
  (no SD swap file), the on-board `goblin-watch`, the kernel-message log, the
  weekly yt-dlp timer, the zsh login shell and read aloud.

- New: `readaloud`, an EPUB3 read-along player. It renders the book's own XHTML
  in Chromium and drives the narration from the SMIL media overlays, filling
  each word karaoke-style at the pace of the track and keeping the current
  sentence in view. Per-book position and speed are remembered, and the
  launcher is in the app menu. Text size is adjustable, the pad works in
  gamepad mode (A play, B replay sentence, X/Y text size, shoulders and
  left/right change chapter, up/down change speed), and pulling the headphones
  out pauses the narration. The list shows a cover and per-book progress;
  parses are cached and the book JSON is served gzipped (2 MB -> 146 KB), and a
  spinner covers the first open. `S` switches to a Spritz view: one word at a
  time, recognition point on the centre line, paced by the narration. The list
  reads title, subtitle, author and series from the epub package (cached next
  to the cover), and closing a book returns to the list instead of exiting.
  Books without media overlays still open: the spine is used as the reading
  order and Spritz runs on a words-per-minute timer (60-900 wpm) instead of the
  narration. The library server is detached from the window, so closing a book
  or the app never leaves the browser pointing at a dead port; `readaloud
  --stop` shuts it down. Books that carry narration are marked with a badge on
  the cover, and the words-per-minute reader marks the live word on the page
  (with its recognition letter coloured) instead of forcing the Spritz view.
  Playback speed and wpm survive chapter changes and are remembered across
  books, not just within one. A chapter picker (real titles from the nav/NCX)
  and a scrubber give coarse and fine seeking; the pad drives the list, the
  transport and the picker. When a Storyteller server is configured in
  `~/.config/readaloud/config.json` the home screen also lists its library,
  marking what is downloaded here; it loads after the local list and silently
  falls back to the cache, so a dead server never blocks navigation. The home
  screen opens with a Continue section: the last three books you were in, most
  recent first, the rest alphabetically below. Storyteller rows carry their
  covers too, proxied and cached on first view, and a page-level error handler
  prints failures in the list instead of showing an empty screen. The library
  has three views, cycled with the header button, `v` or the pad: list, a cover
  grid, and an iPod-style 3D cover flow where the focused cover faces front and
  its neighbours rotate away. Storyteller rows group by series, can be
  downloaded to the library with a live byte bar, and say so when the server is
  unreachable. The bar shows battery. A `<book>.words.json` sidecar, if
  one is ever produced, gives the karaoke exact per-word timings. While playing,
  the transport and scrubber fade out after a few idle seconds so the page uses
  the whole panel; moving, pressing a key or a pad button brings them back, and
  the picker can turn the behaviour off.

- Fix: the Spritz view crashed on every book (it handed plain strings to a
  helper that expected DOM nodes). `tests/test_readaloud.py` now covers the
  parsers, the HTTP surface, range requests and a headless player load, with a
  `?check=1` hook that exercises the string/node word-timing path.

- New: read aloud plays `.m4b`/`.m4a` audiobooks when there is no epub, drawing
  an old compact cassette that fills the panel instead of the book view. The
  cover is printed on the tape label (pre-cropped, warm paper tint, grain and
  gloss), the two reels turn at the playback speed and freeze on pause, the
  tape pack shrinks and fills with progress, and the counter shows elapsed
  time. Metadata, cover and chapters come from the MP4 boxes (Nero `chpl` or
  the QuickTime chapter track) with a cached parse, the file is streamed with
  byte ranges, and the pad, scrubber, chapter picker, themes and remembered
  position work as in the reader.

- Perf: covers are cached as 96 px thumbnails, list images lazy-decode, and
  Storyteller series are collapsed and built only when opened. On the RG35XX H
  the library went from 672 MB resident to 431 MB, and the Storyteller section
  no longer fetches 84 covers up front. Spritz also caches its word timings per
  paragraph instead of rebuilding them every animation frame. `--open` also
  closes any previous player window first: stacked instances were the easiest
  way to eat the handheld's 1 GB.

- Perf: the parsed book is cached on disk next to the covers, so a first open
  is 0.16 s instead of 2.1 s (and 0.23 s instead of 3.0 s for a 29-chapter
  book). Parses are capped at four in memory. Thumbnails are made once by a
  one-shot worker with a single ffmpeg thread and reused forever; images carry
  explicit width/height so scrolling never reflows. Row opacity, smooth
  scrolling and `content-visibility` are gone: they cost compositing on this
  GPU, and the reader scrolls instantly now. Series headers are obviously
  clickable (pointer, chevron, "tap to open"), undownloaded Storyteller rows
  show a download icon on hover/focus and swap it for a spinner plus a byte
  count while the file streams. Thumbnails are validated on read, and covers are
  served `no-cache` so a half-written one cannot stick for a day, and a book
  whose cover was cached as missing is re-extracted instead of showing forever
  blank. Covers no longer use `decoding="async"`: on this GPU Chromium decoded
  them off-thread and never composited the bitmap, so a valid JPEG request still
  painted nothing. Storyteller rows group by the server's real series relation
  (name + position), not by collection, with near-duplicate names normalised, so
  editions no longer split a series and volumes sort by their number.

- Tests: the player and the library expose a `?check=ui` harness that drives the
  real UI with clicks and a synthetic gamepad (picker, chapter jump, spritz
  toggle, play, font, speed, shoulders, scrubber, view cycling, series expand),
  reported as `UITESTS n/n` in the title and asserted by the browser tests. The
  picker rows were not clickable at all; they are now.

- Themes: twelve palettes (Midnight, Amoled, Night, Candle, Slate, Nord, Gruvbox,
  Solarized, Rose Pine, Sepia, Daylight, Paper, plus explicit Black and Dark
  white-on-dark options) driven by CSS variables, switched from a preview sheet
  in the library header (`t` or the palette button) or by cycling from the
  player's picker. Each theme also sets the book page background and ink, so
  "Candle" is a warm dark page and "Sepia" a paper one, and the book's own
  scrollbar follows. Scrollbars are thin and themed instead of the default grey:
  the track is the page colour and the thumb a mix of accent and page, so no
  light strip ever shows up next to a dark page.

- Docs: `docs/performance.md` records how to measure scroll, memory and cold
  open on this device, the numbers before/after, and every trap found so far
  (row opacity, hidden rows, encoding in the request path, transforms that break
  on Panfrost, cached broken images). `AGENTS.md` now makes those measurements
  mandatory after any UI change.

- Fix: mpv no longer drops the video track on software-decoded files. The
  `dmabuf-wayland` VO only accepts dmabuf frames and mpv does not fall back to
  the next VO when the filter chain fails, so every AV1 file (off the hwdec
  whitelist) played audio with no picture; `scripts/vo-by-codec.lua` now picks
  the VO from the file's video codec.

- Fix: Cedrus padding clears now respect planar and semiplanar layouts and odd
  heights; the VP9 decode gate compares 10-bit frames as P010.

- New: VP9 decodes on the VPU, and so does H.265 Main10. The video engine on
  this SoC has a VP9 decoder in the H.265 slot that mainline cedrus never
  driver'd; the image now carries Jernej Skrabec's out-of-tree series (from
  LibreELEC's Allwinner patch set, authors and per-patch purpose in
  `build/kernel/libreelec/README.md`) plus the `v4l2-vp9` helper module it
  needs, which ROCKNIX does not ship. Output is bit-identical to a software
  decode at 720p, 854x480, 1366x768, 1080p and 4K, 8- and 10-bit
  (`PSNR average:inf`). One fix on top is ours: the VP9 backend kept the
  vendor's `SCALE1_STRIDE_ALIGN(1)` (16-byte stride) after `0002` made the
  capture stride 64-byte aligned, so key frames decoded and every inter frame
  read its references with the wrong stride - invisible at 1280/1920/3840,
  broken at 416/854/1366. `0430-cedrus-vp9-stride-align.patch` derives the
  field from `bytesperline`; the patch header has the align sweep and
  `docs/video-decode.md` the details. 10-bit also needed `0414` (H.265 P010
  output): without it HEVC Main10 decoded to garbage, which is why it is in
  the set. Measured with mpv on 1080p24: 11 % of one core zero-copy against
  107 % in software, 9 % at 720p, 13 % at 4K, and a 5-minute soak showed flat
  memory/CMA and no decoder errors. `mpv.conf` now lists `vp9` in
  `hwdec-codecs` and prefers `vo=dmabuf-wayland` (subtitles and OSD verified
  there), and `tools/check-video-decode.sh` gates VP9 against a software
  decode, including a width that is not a multiple of 64, and 8- and 10-bit
  both. Two caveats, both in `docs/video-decode.md`: Chromium's VA path shows up
  to 15 rows of padding at the bottom of clips whose height is not a multiple of
  16 (the driver reports a 16-aligned height on purpose; making it report the
  coded height hangs the engine), and 10-bit at such heights (234, 360) is close
  but not bit-exact (32.8/59.9 dB) while 480/576/720/1080 are `inf`. YouTube:
  the browser still decodes on the CPU (~280 % of one core for AV1, ~240 % with
  VP9 forced) because Chromium's MSE path does not hand frames to VA-API in this
  build; a two-file extension in the image
  (`/usr/lib/handtop/yt-prefer-vp9`, off by default) makes YouTube serve VP9
  instead of AV1, which is still software - it costs about the same, so it is
  left disabled. The VPU path for YouTube is the native client: `goblin-tv` ->
  `goblin-watch` -> mpv plays it zero-copy at ~21 % of one core. Details and
  everything tried in `docs/video-decode.md`.


- Fix: `04c` uses upstream's checks again (`grep -w … >/dev/null`, not `grep -qw`):
  with `pipefail`, `-q` stops reading ffmpeg's long list at the first match, grep
  dies of SIGPIPE and the build fails on a check that actually passed. The
  ffmpeg build itself is upstream's verbatim (Kwiboo `fad85d9` + the drm patch),
  so an upstream bump lands without a conflict — the fork's video work sits in
  `04e` (VA-API), beside ffmpeg rather than inside it.

- Change: the client is called `jellyfin` everywhere, not just in the drawer:
  `/usr/local/bin/jellyfin`, `/etc/default/jellyfin` (was `goblin-dash`),
  `~/.local/state/jellyfin`, `JELLYFIN_*` tunables, `docs/jellyfin.md`,
  `tools/test-jellyfin-tui.py`, `tools/jellyfin-mock.py`, and
  `tools/deploy.sh jellyfin`. `deploy.sh` moves the old config file and state
  directory over, so a hot-deployed device keeps its server key and positions.
  Streams keeps its name (`goblin-tv`, `goblin-watch`).

- Change: the client is called **Jellyfin** in the app drawer, with a pixel
  Jellyfin mark (white on a purple tile) instead of the handheld-with-a-play
  icon. `jellyfin.desktop` / `app-jellyfin.png`; the binary is still `goblin`,
  the drawer entry is just what you see.

- Change: Streams asks what to watch on launch — Twitch or YouTube — instead of
  landing on YouTube's topic list; Esc from either source returns to that
  question. One Enter gets from opening the app to live streams, the other to
  YouTube search/topics.

- Fix: Streams searches Twitch, keeps the cursor where you put it, and shows
  YouTube. One box now does both jobs — typing filters the visible list, Enter
  searches the current source: YouTube videos under `1`, **Twitch channels**
  under `2`/`3` (public GQL `searchFor(userQuery:)`, live channels first, offline
  ones marked and sorted last). `1` lands on a few topic shortcuts (Music,
  Gaming, …) instead of an empty screen, `/` focuses the box, B/Esc clears it.
  The focus bug came from rebuilding the list on every keystroke and focusing it
  each time; the list now takes focus only after a load.

- Feature: **Streams** (`goblin-tv`), a keypad-first browser next to `goblin`:
  Twitch opens on the top live streams, `3` lists the top categories and Enter
  drills into a category; `1` searches YouTube (yt-dlp), Enter plays any row
  through `goblin-watch` fullscreen and Esc returns to the list. No API keys:
  YouTube via yt-dlp, Twitch via its public web GQL endpoint. Ships with a
  pixel-art icon (`app-streams.png`, generated by `tools/icons/gen_app_icons.py`)
  and its own desktop entry. Verified on the device: 28 live streams on launch,
  25 YouTube results for a query, fullscreen VPU playback of a picked result,
  categories → streams. Titles are rendered as plain rich text — Twitch titles
  contain `[`, which Textual would otherwise parse as markup. Also: `/` filters
  the current list by title/channel/game as you type (Esc clears), `4` shows the
  last 50 played items (`~/.local/state/goblin-tv/recent.json`), and `5`
  switches between 480p and 720p. Playback now defaults to **480p**: on the
  640×480 panel it is 29 % of one core against 49 % for 720p, with no visible
  difference (measured on the same video); `GOBLIN_WATCH_MAX_HEIGHT` overrides
  it for `goblin-watch` outside the TUI. While a stream plays, the keys are the
  same as in the goblin client (`/etc/mpv/input-handtop.conf`): B/Esc closes it
  and returns to the list that launched it, D-pad seeks, up/down changes speed,
  A resets, Y pauses, X cycles subtitles — `goblin-watch` now passes that
  `--input-conf` (before, mpv's built-in Esc was "cycle pause", so B did not
  close anything) and keeps mpv off the tty so the TUI is restored untouched.

- Change: no more swap on the microSD. zram now takes all of RAM (zstd, ~2-3 GB
  of compressed swap, no flash writes) and the 2 GB `/swapfile` behind it is
  gone (`rg35xxh-swapfile` removed). Paging to the card was slow enough to look
  like a hang — the Oct 2026 hard locks happened with Chromium near 1 GB RSS on
  a 975 MB board. `earlyoom` (act below 5 % free RAM or RAM+swap, preferring
  chromium) now kills the browser instead of freezing the device.

- Feature: `rg35xxh-ytdlp-update.timer` upgrades the pinned yt-dlp weekly
  (Mon 04:00, randomised, `Persistent=true`), because YouTube's extractor
  changes break a stale yt-dlp within weeks. `goblin-watch` itself is unchanged.

- Fix: kernel messages are logged to a file again. On this image journald never
  imports `/dev/kmsg` (a probe written there shows in `dmesg` and never appears
  in `journalctl -k`, even after restarting journald), so the 2026-10-23 hangs
  left no kernel trace at all. `rg35xxh-kmsg-log.service` runs
  `dmesg --follow` into `/var/log/kmsg.log`, which is the file to read first
  after a crash.

- Feature: `goblin-watch <url>` plays YouTube/Twitch on the VPU. yt-dlp
  (installed with `pipx install --global` by `build/04f-streaming.sh`; the
  Debian package is too old for YouTube and fails with "The page needs to be
  reloaded") extracts, mpv plays. The wrapper prefers H.264 — the only codec
  Cedrus decodes, so YouTube's default VP9/AV1 does not silently fall back to
  software — caps at 720p for the 640×480 panel, and passes node as yt-dlp's
  JavaScript runtime (nodejs is already in the image). Measured 720p60 H.264
  from YouTube: 47 % of one core, 144 MB RSS, zero-copy
  (`VO: [gpu] drm_prime[nv12]`), against 154–174 % and ~1 GB for the same video
  in Chromium, and against VLC, which cannot play YouTube at all (DASH only, no
  progressive format, and VLC cannot mux a video-only and an audio-only URL).
  Twitch works in either player (muxed HLS).

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

- Change: the image ships **zsh as the login shell** with the shell setup the handheld has been running: `zsh` joins `base.list`, `05-configure-base.sh` sets it for `rg`, and `/etc/skel/.zshrc` (Oh My Zsh + `git`/`docker`/`zsh-autosuggestions`/`zsh-syntax-highlighting` + starship) is copied into every fresh home. Oh My Zsh and the two custom plugins come from the new `build/04d-ohmyzsh.sh`, pinned to the revisions the device runs. Until now the environment had to be recreated by hand after a reflash; a reflash now keeps it. The `overlay/etc/zsh/zprofile` hook above is what starts the desktop on a zsh login shell.
- Fix: switching the login shell to zsh left the device on a bare tty1 shell after a reboot (no desktop). The session launcher is `/etc/profile.d/zz-rg35xxh-session.sh` and Debian's zsh does not read `/etc/profile`, so it never ran; the overlay now ships `/etc/zsh/zprofile` with `emulate sh -c 'source /etc/profile'`, which restores `/etc/profile.d` (session launcher, dev-tools PATH) for zsh login shells.

## v0.3.8

- ⚠️ **Known issue (still open):** Bluetooth is sometimes missing on the first boot after flashing. Restart once (Power → Restart); it works from then on.
- **New: low-battery warning and shutdown.** At 10 % a warning stays on screen until tapped and the handheld buzzes three times; at 5 % it shuts down cleanly after a 3-minute countdown, which plugging in the charger cancels. Before, only Screen off did this; in normal use the battery could run flat, which can damage the SD card's filesystem. Levels in `/etc/rg35xxh/power.conf` (`LOW_BATTERY_WARN_PCT`, `LOW_BATTERY_SHUTDOWN_PCT`, 0 = off).
- **New: Battery saver.** One switch caps the CPU at 1.0 GHz (from 1.4 GHz) and halves the screen brightness; turning it off puts both back. Switch it with the new **Battery saver** button in the power menu (works over fullscreen apps too) or by tapping the battery on the taskbar, which gets a green outline while it is on. It stays on across reboots. Wi-Fi power save stays off on purpose (it could stall the Wi-Fi). How much it saves is not measured yet; most of it should come from the dimmer screen. The power menu is now a 3 + 2 grid: Sleep, Restart, Shut down / Battery saver, Log out.
- **Fixed: 10-bit VP9 and HEVC are now exact at every width.** 10-bit VP9 at some widths (for example 352, 416, 480, 544, 1282) was close to the software result but not identical, and 10-bit HEVC at 1282 pixels wide was visibly wrong. The decoder now uses Jernej Skrabec's buffer layout fix from LibreELEC (`0438`), which replaces two of our own patches (`0900`, `0902`); every clip in a 25-clip test (VP9 8/10-bit, HEVC 8/10-bit, H.264, VP8, MPEG-2) matches the software decode bit for bit. Limit, unchanged: 10-bit VP9 at 4K doesn't fit in the decoder's memory. Closes #8.
- **For builders:** the weekly upstream check now watches Arm's GNU toolchain releases (`arm-gnu`). ROCKNIX releases built with GCC 16 wait until Arm publishes GCC 16, so our kernel modules keep being built with the same compiler as ROCKNIX's kernel (`docs/kernel.md`).

## v0.3.7

- ⚠️ **Known issue (still open):** Bluetooth is sometimes missing on the first boot after flashing. Restart once (Power → Restart); it works from then on.
- **New: VP9 decodes on the VPU, 8- and 10-bit.** The H616/H700 video engine has a VP9 decoder in the H.265 slot, but mainline cedrus has no backend for it. The image now carries Jernej Skrabec's out-of-tree series from LibreELEC's Allwinner patch set (a snapshot of 2026-11-01; files, authors, per-patch purpose and what is deliberately left out in `build/kernel/libreelec/README.md`) plus the `v4l2-vp9` helper module it needs, which ROCKNIX does not ship; `build/06b-cedrus.sh` applies the series with `--fuzz=0`, builds both modules and checks their symbol versions against ROCKNIX's own. Output is bit-identical to software at 416x234, 720p, 854x480, 1366x768, 1080p and 4K 8-bit, and at 384x216, 448x256, 512x288, 640x360, 720p, 854x480 and 1366x768 10-bit (`PSNR average:inf`). CPU on paced 1080p24: 11 % of one core zero-copy on the shipped VO (21 % on `vo=gpu`) against 107 % in software; 9 % at 720p, 13 % at 4K. Three fixes on top of the series are ours: `0900-cedrus-vp9-stride-align.patch` (the backend kept the vendor's 16-byte reference-stride alignment after the capture stride became 64-byte aligned, which broke every width not a multiple of 64) and `0901-cedrus-clear-padding-all-codecs.patch` (the 16-line capture padding is now cleared with neutral chroma, so consumers that do not crop, such as Chromium's VA-API path, do not show a line of stale colour) and `0902-cedrus-2bit-plane-size.patch` (10-bit VP9 at widths 128k+1 to 128k+3, such as 1282, wrote past the end of the decode buffer; found by @stockmind in #8). `mpv.conf` adds `vp9` to `hwdec-codecs`, and `tools/check-video-decode.sh` gates VP9 against a software decode, including an off-64 width. The YouTube entry in v0.3.6 says the engine cannot decode VP9; with this it can, but Chromium stays on H.264 through the enhanced-h264ify policy, so the browser does not depend on this out-of-tree backend. VP9 serves local files, other sites and clients such as mpv, ffmpeg and VLC. Limits: 10-bit at widths 32 bytes past a 64-byte multiple (352, 416, 480, 544) is 25-29 dB and not exact, and AV1 stays software. Details in `docs/video-decode.md`.
- Change: mpv's default video output is `vo=dmabuf-wayland,gpu` (was `vo=gpu`). dmabuf-wayland hands the decoder's dmabufs straight to the compositor and costs about half the CPU of the gpu VO (paced 1080p24 VP9: 11 % of one core against 21 %), and subtitles and OSD were verified to render on it. Trade-off: it only accepts dmabuf frames and mpv does not fall back when a VO rejects frames after initialising, so `overlay/etc/mpv/scripts/vo-by-codec.lua` sets `vo=gpu` for codecs outside `hwdec-codecs` (AV1); the cost is one extra script and a choice keyed on the codec whitelist rather than on what the decoder actually did.
- New: the screen dims 10 seconds before auto-sleep, as a warning; touch anything and it comes back and the 10 minutes start over. Only when a sleep would really follow (not while charging, in controller modes, with HDMI or in Screen off). Seconds in `/etc/rg35xxh/power.conf` (`AUTOSLEEP_DIM_SECONDS`, 0 = off).
- Fixed: in the power menu, Sleep no longer stays highlighted while the pointer is on another button, and the four buttons are the same width (the right column was wider).

## v0.3.6

- **This release carries security fixes** (FFmpeg, Bluetooth pairing): reflash to get them; installed handhelds don't receive them any other way yet. Most of the fixes below come from an external review of the whole codebase; the report and what was done about each finding are in `docs/audits/`.
- ⚠️ **Known issue (still open):** Bluetooth is sometimes missing on the first boot after flashing. Restart once (Power → Restart); it works from then on.
- **Security: FFmpeg brought up to 7.1.5.** The hardware-decoding FFmpeg in the image was based on FFmpeg 7.1.3, while Debian ships 7.1.5: about 390 upstream commits behind, among them two security fixes for crafted media files (CVE-2026-8461, CVE-2026-38347). Because these libraries replace Debian's and are held, Debian's own updates never reached them. They are now built from 7.1.5, the same release as Debian's, with the same hardware decoding. `ffmpeg -version` shows `7.1.5-handtop-v4l2request-…`. Reflash to get it.
- **Security: Bluetooth controller modes no longer accept everything.** While a Bluetooth mode was waiting for a PC or Switch, any device nearby could pair, and in Bluetooth: Xbox it was trusted for good, so it could have posed as a keyboard. Now each mode accepts only what a controller needs, Bluetooth keyboards and mice can't connect to the handheld while a mode is on (your own ones pause and come back afterwards), only the device that actually uses the handheld as a controller is trusted, and anything else that paired during the mode is unpaired when it ends. Pairing works as before, with no extra steps.
- **YouTube plays on the hardware decoder in Chromium.** YouTube normally sends VP9 or AV1, which the handheld's video engine can't decode, so it played on the CPU. Chromium now installs the enhanced-h264ify extension on first launch (like uBlock Origin Lite), which makes YouTube send H.264 instead (up to 1080p), and that plays on the video engine. You can change what it blocks from its toolbar button. **Pick 480p** in YouTube's quality menu: the screen is 640×480, so higher shows nothing more and only costs CPU (1080p plays but drops a few frames).
- **Chromium and VLC decode on the VPU.** Both speak VA-API, which Debian does not connect to the stateless V4L2 decoder, so they were software-only. The image now ships `libva-v4l2_request` (a VA-API driver over the request API) and the session exports `LIBVA_DRIVER_NAME=v4l2_request`, which makes it the session's VA-API driver: **Chromium then decodes on the VPU with no flags**, and VLC too when it is installed (`apt install vlc`, XWayland). mpv's `hwdec=auto-safe` also moves to `vaapi` for H.264 and HEVC (same zero-copy dmabuf path; `--hwdec=drm` still works through DRM PRIME), and any client that wants another VA driver can still override the variable. The driver carries three fixes: single-planar support (cedrus is not multiplanar, so upstream master refuses it), `vaAcquireBufferHandle()` (VLC's dmabuf probe), and one plane per layer on export (VLC rejects a composite layer and shows a green window). Measured on the device, 1080p24: Chromium 154–174 % of one core against 251–260 % in software, VLC H.264 11 % against 227 %. VP9/AV1 stay software (no Cedrus decoder). Details and verification in `docs/video-decode.md`.
- **Controls are harder to lose.** A typo in `rg35xxh-input.conf` (a value that isn't a number, is out of range, a yes/no that isn't, an unknown key name) used to stop the input daemon, which left the handheld with no buttons; now that one line is ignored, the default is used, and the reason is in `inputd.log`. If the daemon's input handling ever hits an error, it restarts itself within a few seconds instead of leaving the pointer or buttons dead, and a gamepad still held by the previous daemon at start-up is waited for instead of being used half-set-up. Leaving gamepad mode no longer lets a game's last vibration through. The input daemon's code in the image is now owned by root (it was writable by the desktop user).
- **External Controller:** over Bluetooth (Xbox, and Xbox with better compatibility), a button release or a stick returning to the centre could get lost when the radio was busy at that moment, leaving the button held on the PC until the next input; such a report is now sent again a moment later. Stopping USB cable mode while it is still starting up (switching mode, shutting down) now always removes the USB setup cleanly.
- **Logging out (or a crash) during Screen off no longer leaves the next session dark and slow.** Screen off's low-power state (backlight off, three CPU cores offline, audio off) outlived the session, so the new desktop could start with the screen dark and one core. Each session now leaves it first.
- **Buttons no longer get stuck after a busy moment.** If the system was too busy to read the controls for a moment, a button release could get lost and the button stayed held (a mouse button kept dragging, for example). The input daemon now notices the lost input and reads the controls' real state again.
- **Display:** with an HDMI monitor at a scale other than 1 (or rotated), Extend now puts the handheld's screen right below the monitor instead of leaving a gap the pointer couldn't cross. A resolution Test now switches back after 15 s of real time, even if a display command is slow.
- **Wi-Fi from `wifi.txt`:** if NetworkManager refuses the settings (a WPA password must be 8–63 characters), the Wi-Fi profile you already had for that network now stays, instead of being deleted first. The password stays in the file so you can fix it and reboot.
- Building: the launcher (nwg-drawer) is now compiled with Go 1.27.3 (was 1.27.1), which carries Go's latest security fixes.
- Building: the kernel-module steps now work on arm64 build hosts too (they always downloaded the x86_64 compiler), and an edited kernel patch in `build/kernel/` is picked up by the next build (before, the old kernel tree was reused).

## v0.3.5

- ⚠️ **Known issue (still open):** Bluetooth is sometimes missing on the first boot after flashing. Restart once (Power → Restart); it works from then on.
- **Bluetooth Xbox mode: "better compatibility" option.** Some PC Bluetooth adapters (especially cheap clone dongles) won't pair with the handheld's Bluetooth LE Xbox mode even though they work with other controllers. Turn on **Xbox: better compatibility** in the app's Bluetooth card and the handheld becomes an Xbox One S controller over classic Bluetooth instead (pair it again on the PC). Tested with an iPhone so far.
- **Battery saver for External Controller.** A switch in the app (off by default): the handheld's screen turns off 30 s after the other device connects, and the status screen draws much less. Vol+/- or Power shows the screen for 10 s; it also comes back if the connection drops. Measured: about half the CPU use in Bluetooth modes (70 % → 33 % of 4 cores in Xbox mode), plus the display and backlight off.
- **Clearer names on the PC / Switch:** the handheld now shows up as **"Handtop (Xbox)"** (Bluetooth and USB Xbox modes) or **"Handtop (Switch)"** (USB Switch mode); Bluetooth Switch mode has to be called "Pro Controller". Windows keeps showing the old "Handtop Gamepad" for an existing Bluetooth pairing until you remove and pair it again (it works either way).
- **Bluetooth LE mice and keyboards work.** Most current Bluetooth mice and keyboards (and many gamepads) use Bluetooth LE; they paired and connected but did nothing, because ROCKNIX's kernel lacks the driver BlueZ needs for them (uhid). Handtop now adds it.
- **Fixed: the handheld could freeze with the motor buzzing** when a game's vibration kept changing strength (Bluetooth, USB and gamepad mode alike). The cause was a locking bug in ROCKNIX's gamepad driver; Handtop now ships a fixed build of it. Details in `docs/kernel.md`, which also lists every kernel-level difference from ROCKNIX.
- **Switch Controller mode over Bluetooth (experimental).** Apps → External Controller → **Bluetooth: Switch**: the handheld pairs with a Switch as a Pro Controller (Controllers → Change Grip/Order the first time; afterwards it reconnects by itself). Same controls as the USB version (F = Home, F + Select = Capture), and vibration works. While it is on, Bluetooth runs as a Pro Controller: devices connected to the handheld disconnect (the app lists them and asks first), and classic Bluetooth keyboards, mice and controllers stay off until the mode ends. Tested with a PC (Ryujinx), not on a real Switch yet: please report.
- **Switch Controller mode.** Apps → External Controller → **USB cable: Switch** turns the handheld into a wired Nintendo Switch controller. It poses as HORI's licensed wired pad, so the Switch takes it with no setup: connect the right USB-C port to the dock's USB-A port (A-to-C cable), or without the dock through a USB-C OTG adapter. The printed A/B/X/Y match the Switch's; **F = Home** (hold for quick settings), **F + Select = Capture**. No vibration (that pad type has none). On a PC it is a normal gamepad that Steam and emulators like Ryujinx recognise (in Ryujinx pick Pro Controller and rebind A/B/X/Y once). Tested with Ryujinx, not on a real Switch yet: please report how it goes.
- External Controller keeps its two cards; both are split in two, each half with its own icon: **Xbox** (as before) and **Switch**. Its icons now follow the light theme too.
- **Newer screen panel (rev6) works without copying files.** RG35XX H units come with one of two screens, and the newer one showed garbled lines or stayed black until you copied its device tree over `dtb.img` by hand. The handheld now reads which screen it has from the board at every start (the same pin Anbernic's own firmware checks), uses the matching device tree and restarts once if it had to switch. A card moved to a unit with the other screen fixes itself the same way. If it ever picks wrong, write `rev6` or `regular` in `panel.txt` on the boot partition. What it did is in `logs\panel.txt`.
- The rev6 device tree now has hardware video decoding too (copying ROCKNIX's file by hand, as the v0.3.0 notes said, left it out).

## v0.3.0

- ⚠️ **Known issue:** Bluetooth is sometimes missing on the first boot after flashing (no adapter: the Bluetooth icon shows it off and External Controller → Bluetooth can't start). Restart once (Power → Restart); it works from then on.
- **BT Controller mode is now an Xbox controller.** Over Bluetooth the handheld presents itself as an Xbox Wireless Controller (Series X|S, BLE): Windows loads its own Xbox driver, XInput-only games work directly, and **game vibration now works over Bluetooth** too (played on the handheld's motor through the vibration safety gate). Tested on Windows 11. **After updating, remove "Handtop Gamepad" on the PC and pair it again once** (Windows caches the old description). For this, bluetoothd runs with the Xbox controller's device ID while the mode is on and gets its own back afterwards. The v0.2.0 generic gamepad stays available (`RG35XXH_BTPAD_PROFILE=generic`). Details in `docs/apps/external-controller.md`.
- External Controller app waits a little longer for BT mode to start (bluetoothd restarts).
- **Display app** (Apps → Display) replaces the three "Display: …" entries. It **opens by itself when a monitor is plugged in**, on the handheld (the monitor stays dark meanwhile so the pointer can't get lost on it): pick Monitor only / Extend / Mirror, or leave it for 5 s (restarted by any input) to keep the last layout. Pixel-art pictures of each layout, dark/light theme, its own app icon (monitor + HDMI cable + RG35XX H).
- **Resolution and refresh rate** in the Display app: full lists of the monitor's modes, **Test** with a 15 s "Keep this mode?" that switches back by itself, remembered per monitor. Verified: 1080p at 240 Hz works (real 570 MHz signal).
- **Extend** puts the handheld **below** the monitor (centred) instead of to its right.
- **Pointer speed follows the screen:** on a monitor the stick / D-pad pointer moves faster in proportion to its size (1080p ≈ 2.75×; `display_speed_scale`, 0 = off). The handheld's pointer no longer gets libinput acceleration, so its speed is exactly what `input.conf` says.
- D-pad pointer speed is now **half of the stick's** top speed (`dpad_speed_ratio = 0.5`, 225 px/s; it was a fixed 286 px/s) and follows `pointer_max_speed`. An older `dpad_speed` (px/s) in your own config is still understood.
- **Log out cleans up the previous session safely.** In v0.2.0 a log-out left the old session's helpers running (a second input daemon, a second Tailscale icon). Stopping them is new, and its first version froze the whole handheld during development (never released): the old input daemon, which owns the gamepad and vibration motor, was killed while the new one took over. Now there is one daemon at a time, it releases the hardware cleanly on every stop, the next session waits for it, and its on-screen keyboard runs in a separate process so a log-out can't cut it short. If a handheld ever shows only a solid red LED and won't boot, see `docs/flashing.md`.
- **"Controls restarted":** if the input daemon ever stops responding, it is restarted within about 10 s (before, every button including Power stayed dead).
- **Safety review of everything that touches hardware** (`docs/hardware-safety.md`, plus `AGENTS.md` for contributors). Fixes from it: Re-center sticks and leaving gamepad mode stop vibration before releasing it; a failed Wired Controller start no longer leaves the USB port set up; switching from BT Controller to USB cable (or shutting down) while the Bluetooth mode is on no longer hangs for 90 s; External Controller says so if the input daemon isn't running.
- **Screen off** (from a terminal, `rg35xxh-screen-off`) never auto-sleeps any more, so SSH and downloads keep running. At 20 % battery (not charging) the screen comes back on with a warning that stays until tapped and a vibration; at 5 % it shuts down cleanly.
- **Hardware video decoding in mpv and FFmpeg** (H.264, HEVC, MPEG-2, VP8 on the Cedrus VPU, zero-copy) through a V4L2 request-API FFmpeg build (PR #3). Details: `docs/video-decode.md`.
- **Click-to-mount** for the TF2 card and USB sticks in Files (no password), with "inserted" / "removed" toasts; tapping "inserted" opens Files. Eject on SD cards works.
- **BT Controller mode:** no more stick lag on Windows (shorter Bluetooth interval, reports paced); survives a Bluetooth soft block.
- **New look:**
  - Handtop logo, carved logo wallpapers (dark / light), and an animated boot screen: the logo's keyboard types while the live boot log scrolls beside it.
  - Pixel-art mouse cursor (dark-outlined, Adwaita for the rest); applies after logging out and back in.
  - Power menu: pixel-art icons, order Sleep, Restart / Log out, Shut down. Taskbar: Apps button with a 3x3 grid, red power button, even spacing.
  - Default apps renamed with pixel-art icons: Terminal, File Manager, Text Editor, Web Browser, System Monitor, Code Editor, PDF Viewer, Archive Manager (also in window title bars).
  - Wi-Fi and Bluetooth tray icons in pixel art; terminal colours softened to Handtop's palette; the BT / wired input-mode icons got a dark outline.
  - The External Controller status screen follows the theme: solid in dark, hologram in light.
- **On-screen keyboard:** laid out like a real keyboard (staggered rows, Enter and Backspace in their usual places, ↑ above ↓), light theme, a press trace on every typed key, hold A to repeat, L2 = Shift while it is open, badges for the shoulder buttons' keys. It now stays on top of the Apps screen (covering its bottom rows).
- **Volume / brightness bar** rewritten as a small native program (pixel-font level, vertical at the left edge).
- **Bluetooth taskbar icon** without blueman's tray applet (~55 MB less memory): tap for Bluetooth Manager; Bluetooth off is remembered across reboots.
- The Tailscale tray icon no longer goes missing after some boots.

## v0.2.0

- **BT Controller mode** (requested on Reddit by boldiatti): Apps → External Controller turns the handheld into a Bluetooth LE gamepad ("Handtop Gamepad") for a PC or phone; paired devices reconnect automatically; Select + Start + L1 + R1 stops it (Moonlight's quit combo; a long Start press goes to the other device). Classic-Bluetooth accessories on the handheld pause while it is on. Tested with Windows 11. See `docs/apps/external-controller.md`.
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
