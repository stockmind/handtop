# Read aloud

EPUB 3 read-along player. It draws the book's own XHTML in Chromium and drives
the narration from the SMIL media overlays, so the text highlights in time with
the audio; books without narration are read on a words-per-minute timer instead.

## Where it lives

| Path | What |
|---|---|
| `/usr/local/bin/readaloud` | the whole app: HTTP server, parser, player UI (one Python file, stdlib only) |
| `/usr/local/share/applications/readaloud.desktop` | Apps menu entry, runs `readaloud --open` |
| `~/.config/readaloud/config.json` | optional Storyteller server: `{"storyteller": {"url", "username", "password"}}` |
| `~/.cache/readaloud/` | covers, cover thumbnails, parsed books (`.book.json.gz`), server log |
| `~/Downloads` | library folder, configurable with the positional argument |

`readaloud <folder> [--port 8099] [--open|--serve|--stop]`. `--open` starts the
server detached if it is not up, closes any previous player window and opens a
new one; `--serve` is the server itself; `--stop` shuts it down.

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
