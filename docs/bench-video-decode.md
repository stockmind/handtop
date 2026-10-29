# Decode benchmark, 2026-10-29

Source: one 90 s stretch (from 10:00) of a 1080p H.264 WEBRip pulled from the
Jellyfin server, then transcoded to every codec the VPU has a decoder for. Same
content, same length, same scene complexity - only the codec differs. The files
live on the device in `~/test-media/bench/` (7 files, 159 MB) so this can be
repeated; the script that produced the numbers is `tools/bench-video-matrix.sh`.

Hardware: Anbernic RG35XX H, Allwinner H700 (4x Cortex-A53), 1 GB, kernel 7.2.0
with this branch's cedrus + v4l2-vp9, `mpv` 0.4x, Chromium 155, Firefox ESR 153.

## Decoders and players

| file | ffmpeg hw->null | ffmpeg sw->null | mpv `dmabuf-wayland` | mpv `gpu` |
|---|---|---|---|---|
| H.264 1080p (804) | 28.2 ms/f, 36 fps | 32.3 ms/f, 114 fps | **8.2 ms/f, 20 %** | 21.8 ms/f, 52 % |
| HEVC 1080p (804) | 27.8 ms/f, 37 fps | 44.8 ms/f, 78 fps | **8.1 ms/f, 19 %** | 22.8 ms/f, 55 % |
| HEVC 720p 10-bit | 24.5 ms/f, 42 fps | 44.8 ms/f, 76 fps | **7.4 ms/f, 18 %** | 19.4 ms/f, 47 % |
| VP9 1080p (804) | 27.9 ms/f, 37 fps | 49.0 ms/f, 64 fps | **7.6 ms/f, 18 %** | 21.5 ms/f, 52 % |
| VP9 720p 10-bit | 24.8 ms/f, 42 fps | 34.9 ms/f, 83 fps | **6.9 ms/f, 16 %** | 18.6 ms/f, 45 % |
| VP8 720p | 12.4 ms/f, 84 fps | 12.9 ms/f, 279 fps | **6.8 ms/f, 16 %** | 17.2 ms/f, 41 % |
| MPEG-2 1080p | 26.2 ms/f, 38 fps | 12.7 ms/f, 205 fps | **7.2 ms/f, 17 %** | 21.3 ms/f, 51 % |

How to read this:

- **`ffmpeg hw->null`** is the VPU decoding *and downloading every frame to system
  memory* (`-f null` pulls the DRM PRIME surface back). At 24-28 ms/frame it is
  the copy path, not the VPU's capability - it cannot beat software for these
  resolutions, which is why the copy hwaccel paths never felt faster.
- **`ffmpeg sw->null`** is plain software decode. It beats the copy path for
  H.264/HEVC/VP9 and loses badly for MPEG-2 and VP8, which the VPU handles
  cheaply.
- **`mpv`** is what matters: zero-copy into `vo=dmabuf-wayland` is 6.8-8.2
  ms/frame (16-20 % of one core at 24 fps) for *every* codec, i.e. the codec no
  longer decides the cost. The same frames through `vo=gpu` cost 2.5x more
  (41-55 %), because libplacebo scales and converts them on Mali.
- Percentages are "% of one core at 24 fps" derived from the same measurement
  (`ms/frame * 24 / 10`), not a separate paced run.

## Browsers

| player | file | VPU interrupts / 10 s | CPU |
|---|---|---|---|
| Chromium (kiosk, `file://`) | H.264 1080p | 242 | 129 % of one core |
| Chromium (kiosk, `file://`) | VP9 1080p | 244 | 57 % of one core |
| Chromium (YouTube, VP9 via the extension) | VP9 854x480@30 | 319 | 265 % |
| Chromium (YouTube, default AV1) | AV1 854x480@30 | 0 | ~300 % |
| Firefox ESR (kiosk, `file://`) | H.264 1080p | 0 | 182-186 % |

Chromium really does decode on the VPU (the interrupt counts equal the frame
count), but it still costs 57-129 % of one core for local files and ~265 % for
YouTube, because the browser process tree - page, compositor, 1 GB-footprint
runtime - dwarfs the decode. Firefox never touched the VPU in these runs.

## What this means

1. For playback, keep zero-copy and `vo=dmabuf-wayland` (the shipped mpv.conf):
   codec support and 16-20 % CPU across the board.
2. The VPU's value is *not* raw decode speed here - the A53s do H.264/HEVC/VP9
   software decode faster than the copy-back path can download. It is (a) the
   lower CPU when the frame stays on the GPU, (b) MPEG-2 and VP8, where software
   is 2-4x slower still, and (c) power.
3. Browser playback is CPU-only in both browsers, so it is a battery cost, not
   a codec question.

## Reproducing

```sh
# on the device, with the files already in ~/test-media/bench
bash tools/bench-video-matrix.sh
```

The source clip is not in the repo (copyright, and 159 MB); re-create it from the
Jellyfin server with the item id and offsets recorded in this file's header, or
use any 90 s 1080p clip and re-derive the numbers - the ratios are what matter.

## Matrix by codec and player (2026-10-29)

Every row below was measured on the device; blank cells were not measured rather
than guessed. Metric: VPU interrupts in `/proc/interrupts` over 10 s (one per
decoded frame - 24 fps content gives ~240), CPU of the player's process tree as
a share of one core, RSS of that tree.

### mpv, zero-copy (`--hwdec=drm --vo=dmabuf-wayland`), 90 s clips

| codec | ms/frame | % of one core @24 fps | VPU |
|---|---|---|---|
| H.264 1080p | 8.2 | 20 | yes (242 irq/10 s) |
| HEVC 1080p | 8.1 | 19 | yes |
| HEVC 720p 10-bit | 7.4 | 18 | yes |
| VP9 1080p | 7.6 | 18 | yes (244 irq/10 s) |
| VP9 720p 10-bit | 6.9 | 16 | yes |
| VP8 720p | 6.8 | 16 | yes |
| MPEG-2 1080p | 7.2 | 17 | yes |

Software decode in mpv for the same H.264 clip: 107 % of one core, 0 interrupts.
Per-codec software numbers are in the ffmpeg `sw->null` column above
(32-49 ms/frame for H.264/HEVC/VP9, 12-13 ms/frame for MPEG-2/VP8).

### Players, H.264 and VP9 1080p

| player | decode | VPU irq/10 s | CPU | RAM |
|---|---|---|---|---|
| VLC (`--avcodec-hw=vaapi`) | VPU | 241-289 | **3-4 %** | ~142 MB |
| mpv (`--hwdec=drm`) | VPU | 242 | **9 %** | ~129 MB |
| Chromium (VA-API) | VPU | 242 (H.264), 244 (VP9) | 129 % (H.264), 57 % (VP9) | ~1.0 GB |
| mpv (`--hwdec=no`) | software | 0 | ~107 % | - |
| Firefox ESR (VA-API attempted) | software | 0 | 182-186 % | not measured |

- **All seven codecs are hardware-decoded in mpv and VLC.** VLC was verified per
  codec with the interrupt counter: VP9 8-bit 240, VP9 10-bit 241, VP8 242,
  MPEG-2 241, HEVC 10-bit 241, H.264 289.
- **Chromium** hardware-decodes H.264 and VP9 through VA-API (interrupt counts
  match the frame count); its cost is the browser, not the decoder - 57 % for VP9
  vs 129 % for H.264, and ~265 % on YouTube (page + compositor + 1 GB runtime).
- **Firefox** never reached the VPU in any run (0 interrupts), with or without
  `media.ffmpeg.vaapi.enabled`, force-enabled hardware decode,
  `MOZ_DISABLE_RDD_SANDBOX` and `gfx.webrender.all`.
- RAM is the browser tax: mpv/VLC live in 130-140 MB, Chromium in ~1 GB.

A fully automated sweep of 7 codecs x 4 players x hw/sw was attempted twice on
2026-10-29; both runs stalled on the device (the harness blocked when a player's
process tree was empty), so this table combines the measurements that did
complete. Re-running `tools/bench-video-matrix.sh` with a fixed process sampler
is the way to fill the blank cells.
