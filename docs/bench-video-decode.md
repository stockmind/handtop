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

| player | file | CPU |
|---|---|---|
| Chromium (kiosk, `file://`) | H.264 1080p | 129 % of one core |
| Chromium (kiosk, `file://`) | VP9 1080p | 82 % of one core |
| Firefox ESR (kiosk, `file://`) | H.264 1080p | 8 % (video not playing - see below) |

Chromium decodes both on the CPU: libva logs one `decoding ... via /dev/video0`
line at setup and then stops, and 82-129 % of one core matches software decode
rather than the 16-20 % the same codec costs in mpv. Firefox at 8 % is not a
result - the kiosk window was idle in that run (the same run reports no libva
activity at all), so Firefox is unmeasured here. Neither browser is a useful
video player on this device today: the native client
(`goblin-tv` / `goblin-watch` -> mpv) is.

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
