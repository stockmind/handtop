# Read aloud

EPUB 3 read-along player. It draws the book's own XHTML in Chromium and drives
the narration from the SMIL media overlays, so the text highlights in time with
the audio; books without narration are read on a words-per-minute timer instead.

It also plays `.m4b` / `.m4a` audiobooks, which have no text: those open as a
cassette instead (see below). A book that does have narration can switch to
that same listen-only cassette at any time (see "Listening without the page").

## Where it lives

| Path | What |
|---|---|
| `/usr/local/bin/readaloud` | the whole app: HTTP server, parsers, player and tape UI (one Python file, stdlib only) |
| `/usr/local/share/applications/readaloud.desktop` | Apps menu entry, runs `readaloud --open` |
| `~/.config/readaloud/config.json` | optional Storyteller server: `{"storyteller": {"url", "username", "password"}}` |
| `~/.cache/readaloud/` | covers, cover thumbnails, tape labels, parsed books (`.book.json.gz`), parsed tapes (`.audio.json`), server log |
| `~/Downloads` | library folder, configurable with the positional argument |

`readaloud <folder> [--port 8099] [--open|--serve|--stop]`. `--open` starts the
server detached if it is not up, closes any previous player window and opens a
new one; `--serve` is the server itself; `--stop` shuts it down.

## Audiobooks (m4b)

Files ending in `.m4b` or `.m4a` are listed next to the epubs, with their
embedded cover and a cassette badge. Opening one plays the file itself and
draws an old compact cassette that fills the panel: the cover is printed on the
label (pre-cropped server-side to 576x262, warm-paper tint, grain and a gloss
layer), the two reel windows are cut through it, and the reels turn while the
tape plays. One revolution takes 3.4 s at 1.0x, so the reels answer the speed
setting; pausing freezes them where they are. The tape pack on the supply reel
shrinks and the take-up reel fills as the file plays, and the counter shows the
elapsed time. A, the pad and a tap on the cassette toggle playback; B goes back
30 s; shoulders and left/right change chapter, up/down change speed, the
scrubber seeks, `c` opens the chapter picker (with theme and auto-hide rows)
and Esc returns to the library. Position and speed are remembered per file.

Metadata is read straight from the MP4 boxes (title/artist, `mvhd` duration,
the `covr` cover, and chapters from the Nero `chpl` list or the QuickTime
chapter track), so a 1 GB m4b costs a few seeks, not a decode. The parse, the
cover and the label crop are cached on disk keyed on mtime and size. The file is
streamed over HTTP with byte ranges, 64 KB at a time, because Chromium needs
ranges to seek and the file must never be read into memory.

## Listening without the page

A read-aloud epub can be listened to on the cassette too. The tape button in
the transport, `l`, or the "Tape view" row in the chapter picker switches to it;
the library also has a small cassette icon on narrated rows that opens the book
straight on the tape (`?view=tape`). The choice is remembered (`ra:tape`), so a
book reopens the way you left it.

The switch is seamless because it is the same document and the same `<audio>`
element: playback, position, rate and the current sentence carry over, and
the page stops doing its karaoke work while the tape is up. Switching back
re-runs the highlight and scrolls to the live sentence. The tape shows the
cover, book title, author, chapter name/number, elapsed and total time and the
progress percentage; the scrubber, chapter picker, speed, themes and headphone
pause work as before. EPUB durations are estimated by summing each section's
SMIL span, so the time readout is a label, not a seek target; seeking stays on
the exact section/paragraph fraction.

## Skins

Ten skins ship, changed with `k` or the "Tape skin" row in the picker
(stored as `ra:skin`, forced with `?skin=`):

| Skin | Look | Where the info goes |
|---|---|---|
| **Mixtape** | cream shell, the cover printed across the label (whole cover, side bars filled from the cover edge colours), reel windows punched through | title, author and chapter on the printed band; duration top right |
| **Studio** | smoky translucent shell, big reels, top strip with a red rule, red SIDE/chapter blocks, a blended cover print between and under the reels plus a taped-on photo | title/author on the top strip, chapter in the right block, sticker caption with chapter and progress |
| **Slim** | white dictaphone tape: header window, ribbed deck, hand-written bottom sticker | title/chapter/time in the header, author/progress on the sticker with the cover |
| **Chrome** | glossy metal Type IV shell, brushed silver label plate, chrome reels | title/author/chapter on the plate, cover photo inset, duration chip |
| **Clear** | transparent shell with a paper cover insert behind the mechanism, white caption strip | title and chapter on the strip; cover faded behind the reels |
| **Wood** | wooden hi-fi case, brass plate and reel rims, a small VU meter | title on the brass plate, cover photo, chapter, elapsed on the counter |
| **Vinyl** | album sleeve with the cover, a black record with a printed centre label, tonearm | title/author/chapter on the sleeve; the disc label carries the chapter number |
| **MiniDisc** | translucent teal MD cartridge, round window showing the cover, side label strip | title/author/chapter on the strip, centre hub turns, progress on the counter |
| **Walkman** | portable player body, cassette window with cover and reels, five transport keys, speaker grille | title/chapter over the window, elapsed and percentage in the LCD |
| **8-Track** | black cartridge, large cover label, single loop window, PROGRAM branding | title/author/chapter on the label band, cover sticker, counter |

The skins are pure CSS on the same markup; only the cover images differ (a
576x262 label crop and a 360 px square print, both cached). Nothing animates
except the two reels, and switching a skin never touches the audio. The empty
space around the cassette is tinted with two colours sampled from the cover's
border (`/colors/<book>`, an 8x8 decode cached next to the cover, top and bottom
edge averages), so the room around the tape takes on the book's palette instead
of staying black. It is a static gradient: no extra work per frame.

## Controls

| Input | Action |
|---|---|
| pad A / Space | play, pause |
| pad B | replay the current sentence |
| pad LB/RB, ←/→, |‹ ›| | previous / next chapter |
| pad LT/RT | scrub 5 % back / forward |
| pad ↑/↓ | playback speed in 0.10 steps (wpm in 30 steps for plain epubs) |
| pad X/Y | text size |
| pad Back, ☰ button, `c` | chapter picker (real chapter titles, Spritz toggle, auto-hide toggle) |
| `s` / S button | Spritz view: one word at a time, recognition letter on the centre line |
| `l` / tape button | listen-only tape for a read-aloud book (seamless switch) |
| `k` | cycle the cassette skin: Mixtape, Studio, Slim |
| `-` / `=` | text size |
| Esc / ✕ | back to the library |

## Themes

Twelve palettes, switched from the library header (`t` or the palette button)
in a preview sheet, or cycled from the player's picker: Midnight, Amoled, Night,
Candle, Black, Dark, Slate, Nord, Gruvbox, Solarized, Rose Pine, Sepia,
Daylight, Paper. Each one sets both the chrome and the page inside the book, so
`Candle` is warm dark with cream ink, `Sepia` is paper, `Black` is black with
white text. The highlight follows the theme accent (tinted background plus an
accent underline) instead of a fixed yellow. Stored as `ra:theme`; `?theme=<id>`
forces one for a screenshot.

While playing, the transport fades out after ~3 s and any input brings it back;
the picker turns that off. Speed, text size, view style and per-book position are
remembered. Pulling the headphones out pauses the narration.

## Library

Covers and metadata (title, subtitle, author, series) come from each epub's own
package. Books are grouped by series; the last three books opened are listed
under **Continue**. Three view styles cycle with the header button or `v`: list,
cover grid, and a 3D cover flow.

If a Storyteller server is configured, its library is listed below, grouped by
series and dimmed until downloaded. Downloading streams the readaloud epub from
the server to the library folder with a byte-level progress bar; the row becomes
a normal local book afterwards. A slow or dead server never blocks the local
list: the request has short timeouts, the result is cached, and the section is
simply left out when nothing is reachable.

## Tests

```sh
python3 -m unittest discover -s tests
```

Parsers (clock values, paths, nav labels, metadata, sidecar word timings), the
HTTP surface (gzip, range requests, 404s) and a headless Chromium load of both
pages. The player exposes `?check=1` for the JS smoke check.

A sidecar `<book>.words.json` next to an epub (`{"<href>#<frag>": [t0, t1, …]}`,
absolute seconds) gives karaoke and Spritz exact word timings; nothing produces
it today, the estimate is used otherwise.

## Performance

This app is the reason [performance.md](../performance.md) exists: read it
before changing the list, the player or the cover cache.
