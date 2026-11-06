# Performance notes (RG35XX H)

The handheld is a 1 GB Allwinner H700 with a 640x480 panel and a Mali GPU driven
by Panfrost. Chromium is the whole UI, so anything that adds composited layers,
re-decodes images, or blocks the main thread is felt immediately.

## How to measure

The player and the library expose a harness behind `?perf=`:

* `/?perf=idle` - counts animation frames for 3 s, prints `IDLEFPS n`
* `/?perf=scroll` - scrolls the list up and down for 3 s, prints `SCROLLFPS n`
* `/play?book=<name>&check=1` - the JS smoke check (`CHECK OK` in the title)
* `/play?book=<tape>.m4b&perf=idle` - the cassette with the reels spinning,
  prints `TAPEFPS n` (it forces `playing` so the animation is in the sample)

Run it on the device, with logging on, and read the console lines:

```sh
ssh <device> 'XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 \
  chromium --kiosk --enable-logging=stderr --v=0 \
  --app="http://127.0.0.1:8099/?perf=scroll" \
  --user-data-dir=~/.cache/readaloud-chromium' > /tmp/perf.log 2>&1

ssh <device> 'grep -oE "(IDLE|SCROLL)FPS [0-9]+" /tmp/perf.log'   # after ~15 s
```

Memory, with the app open:

```sh
ssh <device> 'free -m | sed -n 2p'          # used / available / swap
ssh <device> 'ps -eo rss,comm --sort=-rss | head'   # who is holding it
```

When killing a browser between runs use `pkill -x chromium`: a `pkill -f`
pattern that also appears in your own command line kills the shell instead, and
a second launch with the same profile silently attaches to the running instance
("Opening in existing browser session.") so the URL never loads.

## Numbers that were measured here

| thing | before | after |
|---|---|---|
| library with 84 Storyteller books | 672 MB used, 84 cover fetches | 369-431 MB, 0 fetches until a series is opened |
| first open of a 13k-par book | 1.85 s (2.9 s for a 29-chapter one) | 0.16 s (0.23 s) |
| cover served to the list | ~300 KB JPEG, 303x475 | 4.5 KB, 96 px thumbnail |
| scroll frame rate | 2 fps | measured after each change; see the rule below |

Scroll was the worst offender and the hardest to see: 2 fps looks like "input is
delayed", not like "the page scrolls slowly".

## What actually hurt

* **Opacity on rows.** `.st.remote{opacity:.4}` gave every one of 84 rows its own
  composited layer. Dim with colour instead.
* **Building rows that are hidden.** Creating all Storyteller rows up front cost
  ~220 MB even collapsed. Build a group's rows the first time it is opened.
* **Encoding thumbnails inside a request.** `ffmpeg` ran on demand, so scrolling
  into new covers spawned encoders and starved both cores. Encode once, off the
  request path, one thread (`-threads 1`), and reuse forever.
* **Par or JSON rebuilt per frame.** Spritz split the paragraph and recomputed
  word timings every animation frame. Cache per `sec:par`.
* **Compositing tricks that break on Panfrost.** `will-change:scroll-position`
  on the list and `translateZ()` on cover-flow items made content disappear
  entirely. Keep transforms inside rotation/scale.
* **`content-visibility:auto`** made scrolling worse, not better, on this GPU.
* **`scroll-behavior:smooth`** repaints the book iframe continuously. Scrolls
  are instant now, and Chromium runs with `--disable-smooth-scrolling`.
* **`decoding="async"` on images.** Chromium decoded covers off the main thread
  and never handed the bitmap to the compositor: every request returned 200 with
  a valid JPEG and the covers still painted blank. Dropping the attribute fixed
  it. If covers go missing again, check this before the cache.
* **Thumbnails written in place.** A request that landed while ffmpeg was writing
  read a half-written file. Encode to `*.tmp.jpg` and `os.replace()` it.
* **Broken cache entries.** `Cache-Control: max-age=86400` on covers made a
  half-written thumbnail stick for a day. Serve covers `no-cache`.
* **Duplicate windows.** Two kiosk instances of the same profile is the easiest
  way to eat the 1 GB. `--open` now closes the previous window first.

## The tape view

The m4b cassette is static artwork plus two spinning reels:

* the shell, label, text and deck are painted once; the label is composed to
  576x262 by `ffmpeg` on the play path (cover centred, side bars from the sampled
  edge colours) and cached, so nothing scales or decodes on a frame;
* the reels are two small elements animated with a CSS `rotate` whose duration
  follows the playback rate. Pausing sets `animation-play-state: paused`, so a
  paused tape costs no frames at all;
* the tape-pack sizes, the counter and the scrubber update on `timeupdate`
  (~4 Hz), not in a rAF loop;
* the paper effect is four static layers (tint, grain, gloss, vignette) with
  `mix-blend-mode`; they are composited once, not per frame. Do not add a
  continuously running filter or WebGL here: the Mali-G31 punishes it and the
  cassette already fills the panel.

## Rule: check performance after every change

Any change to the library, the player, the cover/cache paths or the launch flags
must end with these steps, on the device, before it is called done:

1. run `?perf=idle` and `?perf=scroll`, quote both numbers in the commit or the
   changelog entry;
2. compare against the previous run with `free -m` while the library is open;
3. check that no `ffmpeg` is running once the thumbs are generated
   (`pgrep -xc ffmpeg` must print 0);
4. run `python3 -m unittest discover -s tests` (it covers the parsers, the HTTP
   surface and a headless player load).

A regression in scroll frame rate, or more than ~10 % more resident memory with
the same view open, blocks the change until it is understood. Numbers, not
impressions: "feels slower" has been wrong here before.
