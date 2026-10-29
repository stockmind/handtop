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
