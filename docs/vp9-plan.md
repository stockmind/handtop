# Plan: VP9 hardware decode on the Allwinner H700 (cedrus)

Goal: `vp9_v4l2request` decoding on the VPU in ffmpeg → mpv → Chromium, with
output that matches a software decode. Every milestone ends with a test on the
device and a commit on the fork branch `vp9-cedrus` (patch under
`build/kernel/`), never on main until it decodes correctly.

## Milestones (each one testable, each one a commit)

**M0 — plan + branch + build loop** (no code yet)
- branch `vp9-cedrus` on stockmind/handtop, plan in `docs/vp9-plan.md`
- build the unmodified cedrus module in this container, install on goblin,
  confirm H.264 still decodes (regression gate for every later step)
- test: `ffmpeg -hwaccel v4l2request` on an H.264 file, CPU ~20 %

**M1 — cedrus advertises VP9**
- add `cedrus_vp9.c` with the codec table entry, the V4L2 stateless VP9
  controls, `v4l2_ctrl` handlers that only copy values, `.run` returns
  `-EINVAL`
- test: `v4l2-ctl -d /dev/video0 --list-formats-ext` shows VP9; ffmpeg opens the
  VP9 file and fails at the first frame with our error, not "unrecognised"
- commit: "cedrus: add VP9 codec plumbing"

**M2 — dimensions, tiles, references**
- program fields 24/25/164 (dims), 371/70 + the tile table, 78/79/97/175-183
  (reference slots) using the field table in `vp9-h700-fields.h`
- test: hardware runs, returns `-EIO`/timeout instead of hanging; dmesg clean

**M3 — loop filter + segmentation**
- fields 20/73/192-195/200-201 and 102-104 + 8 segment words
- test: a VP9 frame decodes without a hardware error (picture may still be wrong)

**M4 — probabilities**
- the 3 744-byte block at `ctx+0xe84` → the VE probability table; layout still
  to be confirmed from `libawvp9soft` / `Vp9DecodeFrameTag`
- test: first decoded frame is visually plausible (extract PNG, eyeball)

**M5 — correctness loop**
- compare against `ffmpeg -f rawvideo` software output (PSNR per frame)
- fix field mappings until PSNR > 35 dB on 8/10-bit, 8 frames
- test: `tools/check-video-decode.sh`-style assertion added for VP9

**M6 — players**
- mpv `--hwdec=v4l2request`, then Chromium (VA driver already speaks VP9 via
  `codec_vp9.c`), measure CPU against the 145 % software baseline
- test: 1080p24 VP9 ≤ 40 % of one core, 0 dropped frames

**M7 — 10-bit and edge cases**
- Profile 2 (P010), odd widths (the 64-byte stride rule), tiles/grid
- test: the width matrix 416/544/720/854/1366 + one 10-bit clip

**M8 — send upstream**
- single patch on the kernel side, minimal comments, no device-specific hacks;
  offer to the linux-media list / upstream cedrus maintainers first, and to
  handtop only if asked

## Rules

- every milestone: build module → install → run the test → commit → push branch
- H.264 regression check after every module install (it is the shipped path)
- no milestone is "done" without its test output quoted
- keep `docs/video-decode.md` honest at each step (VP9 still software until M5)
- unknowns to close offline before M4: probability block layout, the last
  header fields of `Vp9DecodeFrameTag`

## Module build loop (no reflash)

The decoder is the only piece that changes, so skip `build/06b-cedrus.sh`'s
full-image path:

```
T=work/kernel/linux-7.2-rocknix-20261001
sudo ARCH=arm64 CROSS_COMPILE=$PWD/work/kernel/gcc15/bin/aarch64-none-linux-gnu- \
     make -C $T -j32 M=drivers/staging/media/sunxi/cedrus modules
scp $T/drivers/staging/media/sunxi/cedrus/sunxi-cedrus.ko goblin:~/
ssh goblin   # install to /lib/modules/7.2.0/extra/, depmod, modprobe -r/+
~/check-video-decode.sh    # H.264 regression gate
```

`make prepare` must have run once in `$T` (the generated `asm/` headers are
pruned when the tree is packed), otherwise the module build stops at
`asm/compiler.h: No such file or directory`.

With the VP9 series the driver also needs the `v4l2-vp9` helper module, which
ROCKNIX does not ship: build it too, refresh the symvers and install both.

```
sudo make -C $T -j32 M=drivers/media/v4l2-core modules
sudo sh -c "cat $T/drivers/media/v4l2-core/Module.symvers >> $T/Module.symvers"
sudo make -C $T -j32 M=drivers/staging/media/sunxi/cedrus modules
# device: install v4l2-vp9.ko -> /lib/modules/7.2.0/kernel/drivers/media/v4l2-core/
#         install sunxi-cedrus.ko -> /lib/modules/7.2.0/extra/, depmod, reload
```

If `.config` gained a symbol (as `select V4L2_VP9` does), `make olddefconfig`
alone leaves `include/config/auto.conf` stale - run `make syncconfig`.

## Progress

**M0 done** (2026-10-29). Module rebuilt from the unmodified tree and reloaded
on the device, H.264 unchanged:

```
ffmpeg -hwaccel v4l2request / check-video-decode.sh
  ok    decodes without crashing (exit 0)
  ok    Cedrus VPU engaged (not software)
  ok    no decode errors
  122 frames decoded; 0 decode errors
mpv --hwdec=v4l2request-copy:  ok    hardware decoding used
RESULT: VPU path NOT working (zero-copy mpv FAIL, pre-existing)
```

CPU for 10 s of 1080p24 H.264 through `v4l2request` + `drm_prime`:
`utime=0.517 stime=0.387 rtime=2.220` = 41 % of one core; that is the number
to keep flat when VP9 lands. The zero-copy mpv failure is the known
`drmprime` EGL interop gap, unrelated to this work.

**M1 done** (2026-10-29). `cedrus_vp9.c` added, the codec is advertised and
the two stateless controls exist; `setup` refuses every job with `-EINVAL`:

```
v4l2-ctl -d /dev/video0 --list-formats-out
  [4]: 'VP9F' (VP9 Frame, compressed)
v4l2-ctl -d /dev/video0 --list-ctrls
  vp9_frame_decode_parameters 0x00a40a2c (vp9-frame)
  vp9_probabilities_updates   0x00a40a2d
dmesg (ffmpeg -hwaccel v4l2request on vp9-720p.mkv):
  cedrus: VP9 1280x720 profile 0, 10/162 header bytes, tiles 2/0
  cedrus: Failed to setup decoding job: -22
```

The H.264 gate above still passes unchanged (same three `ok` lines and the
same pre-existing zero-copy `FAIL`). Note for the check script: it picks the
first video file under `~/Downloads`, so VP9 test clips live in
`~/test-media`, not there, or every run measures VP9 by accident.

**M2-M4 — done, by adopting an existing implementation.** The hand-rolled
parameter-block work (below, kept for the record) was superseded by Jernej
Skrabec's cedrus VP9 series, found on 2026-10-29 via a code search for
`cedrus_vp9` and taken from LibreELEC.tv's Allwinner patch set. Full provenance,
authors and per-file purpose: `build/kernel/libreelec/README.md`. The series is
written against a 7.2 rebase and applies cleanly to the ROCKNIX tree on top of
`build/kernel/0001`/`0002`; its own commit message says the register layout and
the probability-table DMA buffer format were reverse engineered from the same
vendor blob (`libawvp9HwAL.so`) we were picking apart - it shares the H.265
engine slot and register bank, which is why our "block at VE offset 0" reading
could never work.

Applied: `0410` (don't CPU-map source buffers), `0411` (the VP9 backend,
`cedrus_vp9.c`, 1297 lines), `0421` (`select V4L2_VP9`). Downloaded but not
applied yet: `0412`/`0413`/`0415`/`0417`/`0418` (10-bit and mode-bit naming).

**M5 - verified, bit-exact.** 8-bit profile 0 on the device, VPU output against
a software decode of the same clip, 10 frames dumped through
`hwdownload,format=nv12`:

```
720p   60/60 frames, 0 decode errors    PSNR average:inf
1080p  10/10 frames, 0 decode errors    PSNR average:inf (y/u/v all inf)
```

`tools/check-video-decode.sh` now carries that as a gate (it decodes 10 frames
twice and fails below 35 dB); on the device it reports
`ok VP9 goes through the VPU (cedrus)`, `ok VP9 decodes without crashing`,
`ok VP9 output matches software (average:inf)`.

**M6 - done, and well past the target.** mpv with the shipped config
(`vo=dmabuf-wayland`, `hwdec=auto-safe` -> zero-copy `drm`, `vp9` in
`hwdec-codecs`). Paced playback, whole-mpv CPU as a share of one core, 20-30 s
per run:

| content | CPU |
|---|---|
| VP9 720p 8-bit | 9 % |
| VP9 720p 10-bit | 9 % |
| VP9 1080p 8-bit | 11 % |
| VP9 4K (3840x2160) | 13 % |
| VP9 1080p, zero-copy + `vo=gpu` | 21 % |
| VP9 1080p, copy path (`v4l2request-copy`) | 106 % |
| VP9 1080p, software | 107 % |
| H.264 1080p (shipped config) | 15 % |

The plan asked for <= 40 % at 1080p24; the shipped config is 11 %. Zero-copy is
what does it: the copy path downloads every frame and ends up as expensive as
software decoding, which is why `vo=dmabuf-wayland` is now first in `mpv.conf`
(subtitles and OSD were verified to render on it; screenshots taken with a
`.srt` and `--osd-msg1`).

A 5-minute soak of 1080p VP9 with the shipped config: 12 % average CPU, 60/60
samples alive, flat `CmaFree` (105 MB) and RSS (61 MB), no decoder errors, no
dmesg complaints.

Chromium: the VA driver advertises `VAProfileVP9Profile0/Profile2`, ffmpeg's
`vaapi` hwaccel decodes VP9 through `/dev/video0` (0 errors), and a fullscreen
VP9 file in Chromium renders the real picture.

**M7 - 10-bit works, odd widths only zero-copy.** With `0412`/`0413`/`0415`/
`0417`/`0418` added, the capture queue offers P010 and profile 2 decodes
bit-exactly:

```
VP9 10-bit 720p: 60/60 frames, 0 decode errors, PSNR average:inf (p010le)
VP9 8-bit 720p:  identical to software
H.264 1080p:     122 frames, 0 decode errors
```

Widths that are not a multiple of 64 (416, 854, 1366) were the one real bug
left, and it is fixed: the VP9 backend kept the vendor's
`VE_DEC_VP9_SCALE1_STRIDE_ALIGN(1)` (the 16-byte stride value) after
`0002-cedrus-64-byte-stride.patch` made the capture stride 64-byte aligned, so
the engine read references back with the wrong stride - key frames decoded,
inter frames were garbage. Sweeping that 3-bit field from the device showed 3
is the 64-byte value (`inf` at 854x480; 1, 2, 5, 6, 7 stayed at ~9 dB, 0 and 4
in between), and the patch derives it from `bytesperline`. All widths now match
software bit for bit: 416x234, 854x480 (zero-copy and copy), 1280x720,
1366x768, 1920x1080 and 3840x2160, plus 720p P010.

What is left: a 1080p VP9 soak (the earlier "device died" was a Wi-Fi
re-association, not a hang), the copy-path stride bug above, and M8 becomes
"review Jernej's series rather than post a competing one".

## History: the hand-rolled attempt (superseded)

Before finding the LibreELEC series we reverse engineered the vendor decoder
(`libawvp9Hw.so` from the H616 Android image) far enough to recover the whole
VP9 parameter block: 184 words, 353 flushed fields with their masks/shifts
(`docs/vp9-h700-regs.h`), the tile-table format, the reference fields and the
kick sequence. That work is what made the series' register names readable, but
it is not in the build any more - 0411 in `build/kernel/libreelec/` does the
same job, better, and shares the H.265 register bank (our version assumed the
block sat at VE offset 0, which was the wrong bank). The full notes are in the
git history of this file (`git log -p docs/vp9-plan.md`) if that knowledge is
ever needed again.
