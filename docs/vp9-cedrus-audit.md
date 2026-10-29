# VP9 on cedrus (H700) — findings for audit

Written 2026-10-29 at the end of the work, for an agent or person who wants to
check it rather than trust it. Branch `vp9-cedrus`, merged to `main` at
`22b8456`. Everything below says how it was measured and how to re-measure.

## What was changed, and where

| # | change | file(s) | ours? |
|---|---|---|---|
| 1 | VP9 backend for cedrus (H.265 engine slot), P010 output, 10-bit helpers, H.265 P010 | `build/kernel/libreelec/0410…0421` | no — Jernej Skrabec via LibreELEC, see `build/kernel/libreelec/README.md` |
| 2 | VP9 reference stride (`SCALE1_STRIDE_ALIGN`) derived from the reconstruct surface | `build/kernel/libreelec/0430-cedrus-vp9-stride-align.patch` | yes |
| 3 | Clear linear 4:2:0 capture padding rows for every codec, in `cedrus_device_run()` | `build/kernel/libreelec/0432-…` | yes |
| 4 | Ship `v4l2-vp9.ko` (helper module ROCKNIX lacks) + symbol/vermagic checks | `build/06b-cedrus.sh` | yes |
| 5 | mpv defaults: `vo=dmabuf-wayland,gpu`, `vp9` in `hwdec-codecs` | `overlay/etc/mpv/mpv.conf` | yes |
| 6 | YouTube on VP9 (extension hiding AV1 from capability queries) | `overlay/usr/lib/handtop/yt-prefer-vp9/`, `overlay/etc/chromium.d/50-rg35xxh` | yes |
| 7 | Gates and harnesses | `tools/check-video-decode.sh`, `tools/bench-video-matrix.sh`, `tools/vp9-soak.sh`, `tools/check-video-matrix.sh` | yes |

Patch chain order matters: `0001`,`0002` (in `build/kernel/`) then
`build/kernel/libreelec/*` sorted. Verified to apply cleanly from a pristine
cedrus tree (`0001`/`0002` are already in our snapshot, so test the libreelec
set against it). The tree and the patch chain currently differ by one blank line
in `cedrus_vp9.c` — cosmetic, but a from-scratch build should be re-diffed.

## Established by measurement (trust these)

Method note: the only reliable per-frame signal for "did the VPU decode this" is
`/proc/interrupts`, line `1c0e000.video-codec` — one interrupt per decoded
frame. `LIBVA_V4L2_TRACE` prints `decoding … via /dev/video0` **once per decoder
instance**, so counting those lines says nothing about per-frame behaviour. An
earlier conclusion in this session ("Chromium decodes in software") was wrong
because of exactly that mistake.

1. **VP9 8-bit decodes bit-exactly at every width tested** — 416x234, 854x480,
   1280x720, 1366x768, 1920x1080, 3840x2160, 1080p60, 2x2 tiles, and real
   content at 1920x804: `PSNR average:inf` against a software decode, 0 decode
   errors. Reproduce: `tools/check-video-matrix.sh` or the commands in
   `docs/video-decode.md`.
2. **VP9 10-bit (profile 2, P010) is bit-exact when the height is a multiple of
   16** (448x256, 854x480, 1280x720, 1366x768). Heights 234/360/536 are 32-59 dB
   — a known, documented defect, not fixed.
3. **HEVC 8-bit, HEVC Main10, H.264, VP8 decode bit-exactly** on the same
   material (HEVC Main10 needed patch `0414`; without it Main10 was garbage —
   that is why 0414 is in the set).
4. **The reference-stride bug is real and the fix is measurable**: before
   `0430`, inter frames at 416/854/1366 were garbage (PSNR ~9 dB) while key
   frames were fine; sweeping the 3-bit field on the device gave `inf` only for
   values 3 and 4. Deriving it from `cedrus_dst_frame_fmt()` (not
   `ctx->dst_fmt`) is required for 10-bit, whose references live in the hidden
   NV12 surface.
5. **Zero-copy is what makes playback cheap, for every codec.** mpv
   `vo=dmabuf-wayland` 6.8-8.2 ms/frame (16-20 % of one core at 24 fps) for all
   seven codecs; `vo=gpu` is 2.5x more (41-55 %). ffmpeg's hwaccel copy-back
   (`-hwaccel v4l2request -f null`, the players' `*-copy` variants) is *slower*
   than software decode at 1080p — that is a property of the copy path, not of
   the VPU.
6. **Players**: VLC `--avcodec-hw=vaapi` hardware-decodes all seven codecs
   (VPU interrupts 240-289 per 10 s, 3-4 % CPU decode-only); mpv 242 at 9 %;
   Chromium hardware-decodes H.264 and VP9 (242/244 interrupts) but costs
   57-129 % CPU and ~1 GB RAM; Firefox never engaged the VPU in any run
   (0 interrupts, 182-186 %).
7. **YouTube**: default AV1 → 0 VPU interrupts, ~300 % CPU; with the shipped
   extension the player reports `vp09.*` and the VPU decodes 319 interrupts per
   10 s at ~265 % CPU. The browser tax dominates, not the decode.
8. **Stability**: 5-minute soaks of 1080p VP9 playback — 60/60 samples alive,
   flat CmaFree (~105 MB) and RSS (~61 MB), no decoder errors. Two network drops
   during testing were Wi-Fi re-associations, not crashes (uptime kept climbing).
9. **Build path works**: `06b` applies the series, builds `sunxi-cedrus.ko` +
   `v4l2-vp9.ko`, checks symbol versions, installs both; `10-image.sh` produced
   `work/out/handtop-20261029-ef99793.img.xz` with `modules.dep` listing
   `extra/sunxi-cedrus.ko: kernel/drivers/media/v4l2-core/v4l2-vp9.ko` and the
   new mpv.conf inside.

## Claims that are NOT established (do not cite)

1. **Padding-row artifact across codecs is only partly verified visually.** The
   originally reported green/magenta line predated our padding patches, but its
   source file and codec were not recorded. On Goblin, we compared the saved
   pre-neutral-clear module (`d47916f`) and revised module (`97b3647`) using the
   same 1920x804 VP9 film clip in Chromium; both runs hardware-decoded through
   Cedrus with a 1920x816 NV12 capture surface, and neither screenshot showed
   the tinted line. This confirms the symptom does not reproduce on that clip;
   it does not establish that the patch fixes the originally reported video.
   A recreated blue/green/magenta VP9 pattern also decoded through Cedrus, but
   its screenshot captured the desktop rather than playback, so it provides no
   visual result. The original test video remains unidentified, and H.264/HEVC
   have not been visually compared.
2. **Firefox hardware decode** — it plays, but no VA-API activity was ever
   observed. "Unmeasured", not "broken".
3. **Per-codec numbers for Chromium, VLC-software, Firefox RAM** — the automated
   sweep stalled twice (harness bug: the CPU sampler blocks when no process
   matches). Cells are blank in `docs/bench-video-decode.md` on purpose.
4. **Power/battery numbers** — no valid rail measurement was captured; all CPU
   figures are CPU time, not energy.
5. **Cold-flash of the produced image** — the image exists and its contents were
   checked in `work/rootfs`, but it was never flashed; the device under test has
   hand-installed modules.

## Risks a reviewer should weigh

- The padding clear writes to the capture buffer (CPU) every frame for VP9 and
  now for all codecs; ~23 KB/frame at 1080p. It has not been profiled at 4K.
- `0430`'s value 3 was found by sweep, not from documentation; 4 also worked.
  If the stride alignment changes again (e.g. dropping `0002`), this must be
  re-derived — it already is, from `bytesperline`, but the mapping 16/32/64 ->
  1/2/3 is empirical.
- Reporting `ALIGN(h,16)` as the capture height is deliberate: reporting the
  coded height **hangs the engine** at heights not a multiple of 16 and blocks
  system shutdown (reproduced twice). Do not "fix" that without a new idea.
- The v4l2-vp9 helper is a module ROCKNIX does not ship; any future kernel bump
  must rebuild and install it (done in `06b`, with symbol-version checks).
- The YouTube extension silently changes codec negotiation on youtube.com only.
  It is on by default in `chromium.d`; removing the flag restores stock
  behaviour.

## Where the data lives

- `docs/video-decode.md` — user-facing behaviour, codec/player numbers, the
  YouTube story, the two height caveats.
- `docs/bench-video-decode.md` — measurement methods, the 90 s Jellyfin-sourced
  matrix, the codec x player table with VPU interrupt counts.
- `docs/vp9-plan.md` — the original plan, what each milestone delivered, and the
  references/credits section (vendor blob, LibreELEC series, Chen-Yu Tsai's
  upstream H616 patch, Kwiboo FFmpeg, libva-v4l2-request).
- `build/kernel/libreelec/README.md` — per-patch provenance and what we changed.
- Smoke-test media on the device: `~/Downloads/BABYMONSTER-{BATTER-UP,PSYCHO}-*`
  (7 codecs x 2 resolutions each, full length) and `~/test-media/bench/`
  (90 s clips for the matrix).

## How to re-verify in ten minutes

```sh
# on the device
~/check-video-decode.sh                       # H.264 gate + VP9 bit-exactness + 416 width
bash ~/bench-video-matrix.sh                  # (fix the sampler first, see gaps)
# VPU engagement for any player:
awk '/video-codec/{print $2}' /proc/interrupts   # one per decoded frame
# decode correctness for any file:
ffmpeg -hwaccel v4l2request -i F -frames:v 5 -pix_fmt nv12 -f rawvideo a.yuv
ffmpeg -i F -frames:v 5 -pix_fmt nv12 -f rawvideo b.yuv
ffmpeg -f rawvideo -pix_fmt nv12 -s WxH -i a.yuv -f rawvideo -pix_fmt nv12 -s WxH \
       -i b.yuv -lavfi psnr -f null -          # expect average:inf
```
