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

**M2 — in progress.** The vendor stack (recap: `libawvp9Hw.so` on the H616
Android image, artifacts and helper scripts under `/tmp/opencode`, re-fetchable
from the Transpeed 6K image) does not write VE registers field by field. Per
frame it builds a **parameter block in memory** and hands it to the engine:

- `Vp9AsicInit` memsets 0x2e0 bytes at `ctx+0x1c` and presets one field;
- every `Vp9AsicSet*` call is `SetDecRegister(ctx+0x1c, index, value)`, a masked
  read-modify-write into that block; the descriptor table gives
  `{word_offset, mask, shift}` per index, so the offsets in
  `vp9-h700-fields.h` (second column) are **byte offsets inside the block**,
  not `index * 4`;
- `FlushDecRegisters(handle, inst, ctx+0x1c)` pushes the block out,
  `Vp9AsicRun` then writes 0x34/0x38/0x3c and kicks with `0x04`.

Because those kick registers (0x04, 0x34, 0x38, 0x3c) coincide with block words
1, 13, 14 and 15, the block base is the start of the VE window, i.e. VP9 does
not use the H.264/VP8 block at 0x200. 0x04 is both the start bit and the
interrupt/status register (the vendor kernel shim `google_vp9.c` polls
`+0x04 & 0x53900` and writes `0x04 = 0x11` to start).

Semantics recovered so far, mapped onto `struct v4l2_ctrl_vp9_frame`:

| vendor | meaning |
|---|---|
| 24, 25, 164 (`SetPictureDimensions`) | `(w+7)>>3`, `(h+7)>>3`, `((w+7)&~3)>>2` |
| 371 (`SetTileInfo`) | `tile_cols_log2` |
| 70 | tiled flag (`tile_cols_log2 \|\| tile_rows_log2`) |
| 68, 69 | tile column/row counts (`1 << log2`, clamped to 1 when untiled) |
| tile table (`ctx->0x384`, 1776 B) | per tile, 32 bits: `width << 16 \| height`, both in 64-pixel units, rows outer, then a cache flush of the table |
| 175..185 (`SetReferenceFrames`) | per ref slot: buffer index and `(ref_w << 14) / cur_w`, `(ref_h << 14) / cur_h` (the same hscale/vscale rkvdec computes) |
| 20, 73, 192-195, 200-201 (`SetLoopFilter`) | still to decode |
| 102-104, 112-115, 122-135, 142-161, 166-173 (`SetSegmentation`) | 8 segments x features, still to decode |
| `Vp9AsicProbUpdate` | 3744-byte probability block, layout open |

Blocked on: the descriptor table itself (index -> word offset/mask/shift), which
the earlier extraction only resolved for the fields it saw in call arguments
(index 371 had no descriptor row, which is what exposed the mistake), and the
probability block layout. Recovering the table is mechanical: dump the 392
16-byte descriptor entries at vaddr 0xd034 of `libawvp9Hw.so` with
`arm-linux-gnueabihf-objdump`/`readelf`, then re-read the `SetDecRegister`
call sites with the real word offsets instead of the `index * 4` guess.
