# Hardware Video Decoding

## Status

**Working.** The Cedrus VPU decodes H.264 and HEVC (and MPEG-2/VP8/VP9 via the
same hwaccel) both in Moonlight and in the system FFmpeg and mpv.

- **Moonlight** always worked: it links its own FFmpeg with the V4L2 request-API
  patchset and picks the VPU automatically (Settings → video decoder: Automatic).
  Measured 2026-10-09: 1920×1080 60 fps HEVC at 20 Mbps streams at a steady
  59.9 fps with 0 dropped frames, ~5.9 ms per decoded frame, whole device ~37 %
  busy (software decoding at 1080p: ~55 % busy and choppy).
- **System FFmpeg / mpv** needed the same patchset. Debian trixie's FFmpeg 7.1
  ships only the mainline `drm` hwaccel, which does not work against Cedrus
  here, so `build/04c-v4l2-ffmpeg.sh` cross-builds **Kwiboo's FFmpeg**
  (`v4l2-request-n7.1.3` — the V4L2 Request API patchset, upstream PR 20847,
  i.e. the same code Moonlight embeds) and installs it over the system libs. It
  registers the `v4l2request` hwdevice and the
  `h264/hevc/av1/vp8/vp9/mpeg2video_v4l2request` hwaccels; mpv derives its
  `--hwdec=v4l2request[-copy]` values from exactly those, so no mpv patch is
  involved.

Measured on the device 2026-10-17 (kernel 7.2.0, `tools/check-video-decode.sh`):

```
$ ffmpeg -hwaccel v4l2request -i <540p HEVC episode, 23:55> -f null -
[AVHWFramesContext] Using V4L2 media driver cedrus (7.2.0) for S265
[V4L2RequestContext] slice-based decoder with SLICE_PARAMS=1, ENTRY_POINT_OFFSETS=256 and SCALING_MATRIX=1 controls
frame=34405 fps=108 ... speed=4.5x          # whole episode, 0 decode errors, exit 0

$ ffmpeg -hwaccel v4l2request -i <1080p H.264> -t 5 -f null -
[AVHWFramesContext] Using V4L2 media driver cedrus (7.2.0) for S264
122 frames decoded; 0 decode errors; exit 0

$ mpv --hwdec=v4l2request-copy --frames=60 <540p HEVC>
Using hardware decoding (v4l2request-copy).
```

`--hwdec=v4l2request[-copy]` is offered for H.264, HEVC, MPEG-2, VP8, VP9 and
AV1 (AV1/VP9 have no Cedrus support in this kernel, so they fall back).

### Throughput, and why the copy variant

The zero-copy variant cannot be used: `--hwdec=v4l2request` yields dmabuf
frames, mpv has no render-API interop for `AV_HWDEVICE_TYPE_V4L2REQUEST`, and
`--vo=dmabuf-wayland` refuses those frames (`Cannot convert decoder/filter
output to any format supported by the output`). mpv therefore silently falls
back to software with it. Playback uses `--hwdec=v4l2request-copy`, which
downloads each frame to system memory for the VO to upload — a dmabuf → memory
→ texture round trip that costs throughput on this device:

| Path (2026-10-17) | 540p HEVC | 1080p HEVC | 1080p H.264 |
|---|---|---|---|
| `v4l2request-copy`, `vo=null` (decode + download only) | 94 fps | 23 fps | 25 fps |
| `v4l2request-copy`, `vo=gpu` (real playback path) | 45 fps | 15 fps | 16 fps |
| software, `vo=null` | 145 fps | 48 fps | 55 fps |
| software, `vo=gpu` | 174 fps (crashes) | 16 fps | – |

So the copy path is *slower* than software decoding at 540p, and at 1080p the
GPU upload is the bottleneck (~15 fps) for both paths — 1080p HEVC/H.264 plays
below real time in mpv on this device. Zero-copy would remove the round trip and
is the next step if 1080p playback in mpv matters; Moonlight's zero-copy path
already handles 1080p60.

### The Mesa crash on the software path (pre-existing)

`--hwdec=no` with a GPU VO segfaults intermittently, and it is *not* caused by
the patched FFmpeg. Measured 2026-10-17, 12 s of normal playback of a 540p HEVC
file, crashes per 5 runs:

| Configuration | Crashes |
|---|---|
| software + `vo=gpu` | 3 |
| software + `vo=gpu-next` | 5 |
| `v4l2request-copy` + `vo=gpu` | 0 |
| `v4l2request-copy` + `vo=gpu-next` | 0 |

The same loop crashes 1/5 with Debian's **stock** libavcodec installed, and
`gdb` puts the fault in Mesa's panfrost driver on mpv's `vo` thread
(`libgallium-25.0.7-2+deb13u1.so`), not in any `libav*`/`libsw*` library.
Software decoding produces `yuv420p` frames; the hardware copy path produces
`nv12`, which Mesa handles fine. That is why `/etc/mpv/mpv.conf` defaults to
`hwdec=v4l2request-copy`.

### Fixed: a stale second ffmpeg under /usr/local

An earlier revision of `build/04c` installed with `--prefix=/usr/local`. Images
built since kept that copy, and because `/usr/local/bin` precedes `/usr/bin` in
`PATH`, the `ffmpeg` a user ran from a terminal was that old build (`6dbf87a`,
no `v4l2request`), even though mpv — whose loader picks `/usr/lib` first — used
the new one. `04c` now deletes it, and `tools/check-video-decode.sh` fails if
`ffmpeg` does not resolve to `/usr/bin/ffmpeg`.

## How it works

| Piece | What | Where |
|---|---|---|
| Decoder hardware | Allwinner Cedar video engine (same as H6): MPEG-2, H.264, H.265 8/10-bit, VP8. No VP9 yet (separate upstream series), no AV1 (not in hardware). | `video-codec@1c0e000` |
| Kernel driver | Cedrus, V4L2 **stateless** (request API) → `/dev/video0`, `/dev/media0` | `sunxi-cedrus.ko` in `/usr/lib/modules/7.2.0/extra/`, loaded automatically from the DT node |
| Device tree | ROCKNIX DTB + overlay adding the video-engine node | `/boot/firmware/dtb.img` (original kept as `dtb-rocknix.img`) |
| Memory | Decoder buffers come from CMA: `cma=256M` on the kernel command line (ROCKNIX default is 32 MB). Unused CMA stays available to normal programs. 1080p streaming uses ~140 MB. | `extlinux/extlinux.conf` |
| Heap access | dma-buf heaps are `root:root 0600` in the kernel; the overlay's `72-rg35xxh-dma-heap.rules` gives group `video` access, otherwise ffmpeg logs `Unable to open any dma_heap device` and no dmabuf path can allocate. | `overlay/etc/udev/rules.d/` |
| Userspace | `build/04c-v4l2-ffmpeg.sh` installs Kwiboo's FFmpeg (`v4l2request` hwdevice + per-codec hwaccels) over the Debian libs; `/etc/mpv/mpv.conf` selects `hwdec=v4l2request-copy`. Moonlight uses its own bundled FFmpeg. | `build/`, `overlay/etc/mpv/` |

Players:

- **Moonlight** — zero-copy, 1080p60 HEVC works today; nothing to install.
- **mpv / ffmpeg (system)** — hardware decode works via
  `--hwdec=v4l2request-copy` (the default in `/etc/mpv/mpv.conf`) and
  `ffmpeg -hwaccel v4l2request`. Throughput caveats above.
- Not covered: ffplay decodes in software only; VLC has no V4L2 code path at all
  (removed from the image); Firefox cannot use a V4L2 stateless decoder.

## Source

Upstream series "[PATCH v3 0/7] arm64: allwinner: h616: Support Video Engine" (Chen-Yu Tsai, 2026-07-12; reviewed by Jernej Škrabec, DT acked by Rob Herring; DT patches applied to `sunxi/dt-for-7.4` on 2026-10-05). We use:

- **Patch 4/7** (driver, 4 lines): H616 compatible → existing H6 variant. `build/kernel/0001-cedrus-add-h616-variant.patch`.
- **Patch 7/7** (DT node): as an overlay, `build/dts/rg35xxh-video-engine.dtso`, **without the `iommus` property** (see below).

Review notes: all phandles/IDs the node uses exist in 7.2 (`ve_sram`, `sram_c`, `iommu`, `CLK_BUS_VE`/`CLK_VE`/`CLK_MBUS_VE`, `RST_BUS_VE`); `sunxi_sram` already supports `sun50i-h616-ve-sram`; the request API is always built in 7.2.

For the userspace side, the FFmpeg tree is [Kwiboo/FFmpeg](https://github.com/Kwiboo/FFmpeg) branch `v4l2-request-n7.1.3` (pinned by commit in `build/04c-v4l2-ffmpeg.sh`); it is rebased on FFmpeg n7.1.3 and reports the same `libavutil 59.39.100` / `libavcodec 61.19.101` soname ABI as Debian's ffmpeg 7.1.5, so no other package is rebuilt. It is the only tree that has `libavutil/hwcontext_v4l2request.c`.

## Why no IOMMU

With `iommus = <&iommu 3>, <&iommu 2>` (as upstream) the decoder probed, but enabling the IOMMU made the **display engine** (IOMMU master 0, not described as an IOMMU client in the ROCKNIX DT) page-fault at 60 Hz and the screen stayed black. Without `iommus` the decoder uses physically contiguous CMA memory instead; no faults, display normal.

## Building the module (`build/06b-cedrus.sh`)

The ROCKNIX kernel has everything Cedrus needs built in; only the driver is off. Instead of replacing the kernel, the module is built for it:

1. linux 7.2 (sha256 pinned) + ROCKNIX patches from the tag in `ROCKNIX_VERSION` (now `20261001`) (`packages/linux/patches/7.2`, `mainline`, `devices/H700/patches/linux`, same order as ROCKNIX's `package.mk`) + our Cedrus patch.
2. ROCKNIX's own `.config`, extracted from `KERNEL` (`extract-ikconfig`), with `VIDEO_SUNXI_CEDRUS=m`.
3. **GCC 15** (Arm GNU Toolchain 15.2.Rel1, sha256 pinned): ROCKNIX uses GCC 15; with GCC 13 compiler-feature options (`CC_HAS_COUNTED_BY`, …) changed type definitions and 8–50 symbol versions differed.
4. Check: every symbol version the module imports must equal the one ROCKNIX's own modules import, and vermagic must match — otherwise the build stops. (Verified: all 1696 symbols imported by ROCKNIX modules match this build.)

Takes ~6 min on a 28-core x86_64 build host. **When `ROCKNIX_VERSION` changes, this step rebuilds against the new tag automatically**; the checks catch mismatches.

## Undo / fallback

On the boot partition (from Windows): rename `dtb.img` → `dtb-ve.img` and `dtb-rocknix.img` → `dtb.img`. Without the node the module never loads. Optionally remove ` cma=256M` from `extlinux/extlinux.conf`.

Without the VPU, `hwdec=v4l2request-copy` falls back to software automatically
(`--hwdec-software-fallback` defaults to yes) — but note the pre-existing Mesa
crash on that path above; `vo=gpu-next` is worse, not better.

## Display caveat

The decoder claims SRAM C, which the 7.2 source says is toggled together with the display engine's region. No display problems were seen while streaming 1080p, but watch for glitches.
