# Hardware Video Decoding

## Status

**Working.** The Cedrus VPU decodes H.264 and HEVC (and MPEG-2/VP8 — see the
`hwdec-codecs` note below) both in Moonlight and in the system FFmpeg and mpv.

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
  `h264/hevc/av1/vp8/vp9/mpeg2video_v4l2request` hwaccels, and — since
  2026-10-17 — the same decoders again under the `drm` hwdevice
  (`build/patches/ffmpeg-v4l2request-drm.patch`). mpv derives its
  `--hwdec=v4l2request[-copy]` and `--hwdec=drm[-copy]` values from exactly
  those; the `drm` registration is what makes zero-copy playback work, with an
  unpatched mpv (see *Zero-copy* below).

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

`--hwdec=v4l2request[-copy]` and `--hwdec=drm[-copy]` are offered for H.264,
HEVC, MPEG-2, VP8, VP9 and AV1, but mpv only tries the codecs on its hwdec
whitelist, which by default leaves MPEG-2 and VP8 on the CPU
(`[vd] Not trying to use hardware decoding: codec mpeg2video is not on
whitelist`, with any `--hwdec` spelling). `/etc/mpv/mpv.conf` therefore sets
`hwdec-codecs=h264,hevc,mpeg2video,vp8` — that option *replaces* the default
list, so the codecs that matter have to be in it — and all four formats this
kernel's Cedrus has reach the VPU. The whitelist line is worth its keep on
battery: MPEG-2 1080i drops from 88.8 % to 45.6 % CPU and VP8 720p from 92.1 % to
48.1 %, at the same fps.

VP9 is not in the list yet: the driver decodes it (see "VP9" below) but the
player side is still being measured, so mpv keeps decoding VP9 in software.
AV1 is not in the list because the silicon has no AV1 decoder, and mpv's
attempt does not fail cleanly: it reports `Error while decoding frame (hardware
decoding)!` for every frame before it gives up. Leaving them out of the
whitelist means they are never attempted and decode in software right away —
VP9 in FFmpeg's native decoder, AV1 in dav1d (this build enables it: with the
hardware devices advertised, the native av1 decoder picks no pixel format and
renders black).

### VP9

The H616/H700 video engine also decodes VP9, in the same slot as H.265. Mainline
cedrus has no backend for it; this image carries Jernej Skrabec's out-of-tree
series (provenance and applied patches: `build/kernel/libreelec/README.md`),
plus the `v4l2-vp9` helper module it needs, which ROCKNIX does not ship.

Verified on the device 2026-10-29 with 8-bit profile 0, 720p: the VPU decodes
the clip and the frames come out **bit-identical to a software decode**
(`PSNR average:inf`, 60/60 frames, `0 decode errors`); 1080p reports
`0 decode errors` as well. `tools/check-video-decode.sh` has a VP9 section that
decodes 10 frames twice (VPU and software) and fails below 35 dB.

1080p is bit-exact too (`PSNR average:inf`, 10/10 frames). Measured with mpv on
the same clip, 10 s of real-time playback at 24 fps, whole-process CPU as a share
of one core: software 116 %, `--hwdec=v4l2request-copy` 100 %,
`--hwdec=drm` with `vo=gpu` 59 %, `--hwdec=drm` with `vo=dmabuf-wayland` 48 %.
Use `--hwdec=drm`; the `--hwdec=v4l2request` spelling falls back to software for
VP9, and `vp9` has to be added to `hwdec-codecs` before mpv will try it.

Open on this path: the 40 % target is not met yet (48 %), Chromium/VA-API has
not been tried with VP9, 10-bit (profile 2, P010 capture) is prepared but not in
the image, and there is no soak yet for 1080p VP9 (the earlier "device dropped
off the network" was a Wi-Fi re-association, not a hang).

### Throughput: zero-copy vs copy

Two paths reach the VPU, and since 2026-10-17 both work. **Zero-copy**
(`--hwdec=drm`, or `--hwdec=v4l2request` with the patched mpv) hands the decoder's
dmabufs straight to the VO's DRM PRIME interop; the **copy** variants download
every frame to system memory for the VO to upload again. *Zero-copy* below has
the two patches that make the zero-copy names appear; the default configuration
has been switched to them.

Measured 2026-10-17 on the device with `--no-audio --untimed` (the reference
files are 24 fps, so ≥24 fps is real time). Absolute numbers move by tens of
percent between harnesses — audio on, a different frame count — so read the
ratios, not the digits:

| Path | 540p HEVC | 1080p HEVC | 1080p H.264 |
|---|---|---|---|
| zero-copy, `vo=gpu` `--profile=fast` | 79 fps | 51 fps | 43 fps |
| zero-copy, `vo=dmabuf-wayland` | 94 fps | 62 fps | 50 fps |
| zero-copy, `vo=gpu` (default scaler) | 79 fps | 23 fps | 18 fps |
| copy, `vo=gpu` (default scaler) | 78 fps | 18 fps | 18 fps |

The download/upload round trip halves decode throughput at 1080p (99 → 48 fps
HEVC, 51 → 24 fps H.264). At 540p the VPU is nowhere near the bottleneck and the
copy costs little — which is why the first release, whose table used
audio-enabled runs, only saw the copy path lose badly at 1080p.

At 1080p the *renderer* was the other half of the problem: with the default
(high-quality) scaler the `gpu` VO manages 23 fps at 1080p HEVC and 18 fps at
1080p H.264, regardless of zero-copy or copy, because it is spending its time in
the scaler rather than in the decoder. A bilinear scaler (`--profile=fast`)
removes that limit. Ten-second playback runs, dropped frames from
`--term-status-msg='... drop=${frame-drop-count}'`:

| 10 s playback, zero-copy (`hwdec=drm`) | dropped frames |
|---|---|
| 540p HEVC, `vo=gpu` | 0 |
| 540p HEVC episode (23:55, whole file), `vo=gpu` | 0 |
| 1080p HEVC, `vo=gpu` default scaler | 23 |
| 1080p HEVC, `vo=gpu --profile=fast` | 0 |
| 1080p HEVC, `vo=dmabuf-wayland` | 0 |
| 1080p H.264, `vo=gpu` default scaler | 35 |
| 1080p H.264, `vo=gpu --profile=fast` | 0 |
| 1080p H.264, `vo=dmabuf-wayland` | 0 |
| 1080p H.264, `vo=gpu` **copy** path (`drm-copy`), for comparison | 149 |

So `overlay/etc/mpv/mpv.conf` ships `hwdec=auto-safe` — zero-copy first, the copy
variants behind it, software last — plus `profile=fast`. `auto-safe` picks the
zero-copy method by itself (`mpv --hwdec=auto-safe -v` logs `Trying hardware
decoding via hevc-drm`) and skips it when the VO has no usable interop.
`vo=dmabuf-wayland` is faster still but renders video only — no OSD, no
subtitles — so it remains an option rather than the default. The software path is
unchanged and still the unstable one (next section).

### Versus the software path (what an image without this PR does)

Without `04c` mpv has only software decoding, so that is the honest before/after
baseline. Same harness, 120 frames, `vo=gpu --profile=fast`, measured 2026-10-21
on the device (mpv 0.40; `--hwdec=no` on the patched build — its software path is
the same decoders Debian ships):

| 120 frames, `vo=gpu --profile=fast` | software | `hwdec=drm` (zero-copy) |
|---|---|---|
| 540p HEVC | 35.9 fps, 120 % CPU | 36.7 fps, 69 % CPU |
| 1080p HEVC | 30.3 fps, 266 % CPU | 36.1 fps, 75 % CPU |
| 1080p H.264 | 29.0 fps, 271 % CPU | 35.5 fps, 76 % CPU |

CPU is `(user+sys)/wall` for the whole process. The saving is the point: roughly
3.5 CPUs at 1080p, whichever codec. The fps column saturates near 36 fps in this
harness because the `vo=gpu`/panfrost path, not the decoder, is the limit — the
gain there is headroom (audio, subtitles, the desktop, thermals), not raw decode
rate. Decode-only runs show the same from the other side: with `vo=null`
`--hwdec=drm-copy` (VPU plus a download per frame) does 94 / 32 / 23 fps against
software's 154 / 68 / 48 fps, at about a third of the CPU — which is why
zero-copy, not the VPU alone, is what turns the saving into a playback win.
`vo=null` cannot present `drm_prime` frames, so `--hwdec=drm` falls back to
software there and is not a valid way to measure the zero-copy path.

The power draw could not be compared directly: the AXP2202 fuel gauge on this
board reports the same ~423 mA with the SoC idle and with four cores pegged, so
CPU time is the only usable proxy.

### The blue video: the driver's stride, and the fix

Zero-copy (`--hwdec=drm`) used to render a **flat blue rectangle** for streams
whose width is not a multiple of 64 pixels. The picture was not a decode
failure: the decoder produced correct frames, and `MESA: panfrost: rejecting
image due to unsupported offset or stride alignment` was logged for every
frame. Panfrost refused the dmabuf import, the VO kept its clear colour, and
nothing else was drawn.

Measured 2026-10-21 on the device (`--hwdec=drm`, 24 frames each, "Mesa
errors" counted from the mpv log):

| width | Mesa rejections | picture |
|---|---|---|
| 416 (416x234 / 416x236 / 416x238) | 26-62 per frame | blue |
| 544 (544x306) | 26 | blue |
| 720 (720x404) | 26 | blue |
| 512, 640, 704, 960, 1280 | 0 | correct |

Height did not matter (1280x536 was fine, 416x240 was fine), only the width —
i.e. the NV12 stride.

**The cause was the driver, not the GPU.** Mali (this SoC has a Mali-G31,
Utgard) wants a linear surface whose stride *and* plane offsets are 64-byte
aligned, and panfrost enforces that. The Cedrus driver aligned the decoded
picture to **16** bytes (`ALIGN(width, 16)` in `cedrus_prepare_format()`),
which is a multiple of 64 only when the width is a multiple of 64 — hence
416 = 6.5x64, 544 = 8.5x64 and 720 = 11.25x64 failed while 640 = 10x64,
704 = 11x64, 960 = 15x64 and 1280 = 20x64 worked.

The VPU's output stride is programmable (`VE_PRIMARY_FB_LINE_STRIDE`), so
`build/kernel/0002-cedrus-64-byte-stride.patch` aligns the capture stride to
64 bytes and programs the register from the negotiated `bytesperline`, so the
driver and the hardware cannot disagree about the layout. The chroma plane
then starts at `stride * height`, which is 64-byte aligned too.

Measured 2026-10-22 on the device with the patched module:

| width | Mesa rejections | picture |
|---|---|---|
| 416, 544, 720, 854, 1366 | 0 | correct |

The picture was checked against the software-decoded frame: the zero-copy
screen and the software screen differ by 88 dB PSNR (the OSD clock), i.e.
they are the same picture — the VPU writes the frame with the 64-byte stride
and panfrost imports it. The 416-wide H.264 file decodes on the VPU at
16.6x real time with 0 errors, and the 1080p H.264/HEVC, 960x540 and 540p
HEVC files are unchanged.

### Zero-copy for every width

The client streams at the panel resolution and uses zero-copy; nothing
depends on the width any more.

Measured 2026-10-21 on the device (h264, 24 fps, 20 s, `vo=gpu --profile=fast`,
CPU as % of one core):

| resolution | `drm` (zero-copy) | `drm-copy` |
|---|---|---|
| 640x360 (the panel) | 16 % CPU, 0 dropped | 28 % CPU, 0 dropped |
| 960x540 | 17 %, 0 | 45 %, 0 |
| 1280x720 | 17 %, 0 | 62 %, 0 |
| 1920x1080 | 18 %, 0 | 115 %, 19 dropped |

Zero-copy is flat (the VPU and the GPU do the work, the CPU barely moves),
while the copy path scales with the pixel count. That is why the client
streams at the panel resolution *and* uses zero-copy: 16 % CPU instead of the
62 % the old 720p copy stream cost, and no blue frames.

The copy path stays available as a fallback (`--hwdec=drm-copy`, and
`hwdec=auto-safe` keeps it behind the zero-copy method), but the client no
longer has to predict or check the width.

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
`nv12`, which Mesa handles fine. That is why `/etc/mpv/mpv.conf` defaults to `hwdec=auto-safe`: zero-copy
`drm` first, `v4l2request-copy` only when the VO has no usable interop.

## Zero-copy

The decoder was never the problem: FFmpeg's V4L2 request-API code already
produces `AV_PIX_FMT_DRM_PRIME` dmabufs, exactly what a VO's DRM PRIME interop
consumes. The problem was the *device type the decoders were registered under* —
only `AV_HWDEVICE_TYPE_V4L2REQUEST`, while this device's only interop
(`drmprime`, reachable from `vo=gpu` through EGL and from `vo=dmabuf-wayland`)
declares `AV_HWDEVICE_TYPE_DRM`. mpv hands out interop function tables from
`hwdec_get_hwcontext_fns()` for cuda/d3d11/dxva2/vaapi/vdpau/drmprime and nothing
else, so `--hwdec=v4l2request` never received frames it could render and fell back
to software, while `--vo=dmabuf-wayland` refused them outright.

The interop is indifferent to where the dmabuf came from: `hwdec_drmprime.c` only
duplicates the frame's object fds and imports them with
`EGL_EXT_image_dma_buf_import` / `GL_EXT_EGL_image_storage`. Its own device fd is
never used on this panfrost/EGL path, so the device mpv created for the interop
does not have to be the same type as the decoder's. Two small patches make use of
that; the image ships the FFmpeg-side one.

### The patch: `build/patches/ffmpeg-v4l2request-drm.patch`

Applied by `build/04c-v4l2-ffmpeg.sh` right after the pinned Kwiboo checkout.
Three parts:

1. `libavcodec/hwconfig.h` gains `HWACCEL_DRM_V4L2REQUEST(codec)`: the same
   `ff_<codec>_v4l2request_hwaccel`, registered a second time with
   `AV_PIX_FMT_DRM_PRIME` but under `AV_HWDEVICE_TYPE_DRM`. h264dec, hevcdec,
   av1dec, vp8, vp9 and mpeg12dec each add one line beside their existing
   `HWACCEL_V4L2REQUEST(x)`.
2. `libavcodec/v4l2_request.c` (`ff_v4l2_request_init()`) notices when the device
   context the caller supplied is a `drm` device and swaps in a real
   `AV_HWDEVICE_TYPE_V4L2REQUEST` device before calling
   `ff_decode_get_hw_frames_ctx()`. mpv only ever passes the device it created for
   the interop; the decoder needs one of its own type, and it is the *device's*
   hw_type that decides what `av_hwframe_ctx_alloc()` produces.
3. `libavcodec/decode.c` (`ff_get_format()`) picks the hw config whose **device
   type matches the supplied device context** instead of simply the first config
   with a matching pixel format. Without this the first `DRM_PRIME` match — the
   `v4l2request`-typed entry — is chosen and `hwaccel_init()` rejects the DRM
   device:

   ```
   hevc: Invalid setup for format drm_prime: does not match the type of the provided device context.
   ```

   and mpv falls back (that was this patch's first version: `--hwdec=drm` decoded
   in software; the selection fix is what made it work).

Consequence: **stock Debian mpv** — no mpv rebuild anywhere in the image build —
offers `drm` and `drm-copy` in addition to `v4l2request`/`v4l2request-copy`, and
zero-copy renders:

```
$ mpv --hwdec=drm --vo=gpu -v <540p HEVC>
[vo/gpu] Loading hwdec drivers for format: 'drm_prime'
[vo/gpu] Loading hwdec driver 'drmprime'
[vo/gpu/drmprime] Using EGL dmabuf interop via GL_EXT_EGL_image_storage
[vd] Using hardware decoding (drm).
```

The system FFmpeg CLI reaches the same decoder through the same device type. The
node has to be given explicitly — the default `drm` device selection does not work
on this SoC (`Device creation failed: -14`) — and `bench` then reports the same
`cedrus` decode:

```
$ ffmpeg -hwaccel drm -hwaccel_device /dev/dri/renderD128 -i in.mp4 -f null -
```

`--hwdec=drm` also works under `--vo=dmabuf-wayland`, the fastest combination
measured (62 fps at 1080p HEVC, 50 fps at 1080p H.264, 0 dropped frames over 10 s
in both — video only).

### Why the FFmpeg side

- It is one FFmpeg patch, so *every* consumer of `AV_PIX_FMT_DRM_PRIME` gains it:
  stock mpv, the `ffmpeg` CLI, anything else a user installs. Patching mpv
  instead would fix mpv only.
- The image build stays free of a distribution-package rebuild.
- All four spellings keep working — `v4l2request`, `v4l2request-copy`, `drm`,
  `drm-copy` — so existing configurations are not invalidated and the copy path
  remains available as a fallback.

Nothing here needs a newer FFmpeg (`v4l2-request-n8.x`) or a newer mpv, and
Moonlight is unaffected: it embeds its own FFmpeg and never goes through mpv.
The `ff_get_format` change also looks like an upstream FFmpeg fix (a caller that
passes a device of a type other than the codec's first-listed configuration is
rejected today); it is kept as a local patch until that is settled upstream.


## Chromium and the VPU: the VA-API route

When the browser swap landed (v0.1.3) Chromium video was still CPU-decoded
(~195 % of one core at 1080p24 on the 640×480 session). The question was whether
VA-API could reach Cedrus: Chromium cannot speak the kernel's V4L2 stateless API
itself, and Debian ships no VA driver for the VPU. Evaluated 2026-10-17 on the
device; **rejected, nothing shipped.**

**The backend builds — but not the one everyone links to.** The sunxi wiki's
`bootlin/libva-v4l2-request` has not been touched since 2021 and no longer
compiles: it targets the pre-mainline draft API (`V4L2_PIX_FMT_H264_SLICE_RAW`,
`num_slices`, the old MPEG-2 controls — mainline renamed all of them), and its
bundled `h264-ctrls.h`/`hevc-ctrls.h` now clash with the kernel's. The maintained
fork is [sofus13/libva-v4l2_request](https://github.com/sofus13/libva-v4l2_request)
(tag `1.3`, what the Asahi AUR package builds):

```sh
git clone -b master https://github.com/sofus13/libva-v4l2_request.git
cd libva-v4l2_request && meson setup build --prefix=/usr && ninja -C build
install -m755 build/src/v4l2_request_drv_video.so /usr/lib/aarch64-linux-gnu/dri/
# packages: meson ninja-build libva-dev libdrm-dev (+ build-essential for gcc)
```

```sh
$ LIBVA_DRIVER_NAME=v4l2_request vainfo --display drm --device /dev/dri/renderD128
libva-v4l2request: detected 1 Request API decoder
      VAProfileMPEG2Simple/Main, VAProfileH264ConstrainedBaseline/Main/High
      VAProfileHEVCMain/Main10, VAProfileVP8Version0_3 : VAEntrypointVLD
```

— the codecs the VA driver implements. VP9 is an entry the driver only
advertises when the kernel decoder supports it; with this image's cedrus it can
be added, but the player side is still untested (no AV1: not in the silicon).

**Chromium engages it and the VPU decodes.** With `LIBVA_DRIVER_NAME=v4l2_request`
and no VA-specific flags, Chromium 155 builds `VaapiVideoDecoder` and hands the
stream to `/dev/video0`:

```
[VERBOSE2:media/gpu/vaapi/vaapi_video_decoder.cc:136] VaapiVideoDecoder():
libva-v4l2request: decoding h264 via /dev/video0 [cedrus] (media /dev/media0)
libva-v4l2request: using CAPTURE format NV12 (1920x1088)
```

The numbers look like a working hardware path — 1080p24, native Wayland,
`getVideoPlaybackQuality()` reported by the page and CPU sampled from inside the
browser:

| 1080p24 in Chromium | decoder | CPU (one core) | dropped frames |
|---|---|---|---|
| no VA driver (shipped) | software | 185–195 % | 0.3/s |
| `v4l2request` VA driver | Cedrus VPU | **81 %** | 13 in the first 2 s, then **0 over 22 s** |

HEVC decodes the same way (`decoding hevc via /dev/video0 [cedrus]`, 56 % of one
core).

**The picture is green** (fixed on 2026-10-23, see "Chromium is fixed" below).
In every 2026-10-17 screenshot the video area was a flat green rectangle — a
YUV (0,0,0) surface that was never written to the screen. `grim` photographs mpv's VPU-decoded output (`hwdec=drm`) and Chromium's
*software*-decoded video correctly, so it is not a capture artefact; the green
survives every flag combination:

| Chromium + `LIBVA_DRIVER_NAME=v4l2_request` | decoder | CPU | screen |
|---|---|---|---|
| no VA-specific flags | Cedrus | 81 % | green |
| `--enable-features=VaapiVideoDecoder,VaapiIgnoreDriverChecks,AcceleratedVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxZeroCopyGL --use-angle=gl --ignore-gpu-blocklist` | Cedrus | 122 % | green |
| `--use-angle=gles --ignore-gpu-blocklist` | Cedrus | 81 % | green |
| `--disable-features=VaapiVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxGL,AcceleratedVideoDecodeLinuxZeroCopyGL` | software (VA-API dropped) | 185 % | correct |
| `--ozone-platform=x11 --use-angle=gl` (XWayland) | software (`failed to find a suitable render node`) | 182 % | correct |

That fourth row is the dead end: Chromium's Linux VA-API decoder only offers the
GL/texture output path, so turning it off does not make Chromium copy frames out
for display — it makes Chromium stop using VA-API. On that GL path panfrost's EGL
accepts the driver's dmabufs without logging an error and then samples nothing, and
Chromium reports no failure, so there is nothing to fall back on. The other VA-API
consumer on the image cannot even cross-check the driver: `ffmpeg -hwaccel vaapi`
fails earlier, at device setup (`Cannot allocate memory`; CMA is 256 MB, ~60 MB
free), and Debian's mpv is built without VA-API (`Unsupported hwdec: vaapi`).

**Verdict (2026-10-17).** The VPU stays reachable through FFmpeg's own
`v4l2request` hwaccel — mpv, the `ffmpeg` CLI and Moonlight all reach it —
while Chromium video stays software-decoded (it plays 1080p24 in real time at
~2 cores). VLC 3 also went green on this driver, but for a different reason: a
composite descriptor its GL converter rejects. Chromium asks for separate
layers, gets them, and still shows green, so that one is the stale-backing case
described below.

Both were fixed in the driver on 2026-10-23 ("Chromium is fixed", and
"Watching video with VLC"); Chromium video now runs on the VPU too.

### Revisit plan (researched 2026-10-17, device offline; try in this order)

The driver (Ondrej Jirman's fork, tag 1.3 at the time of this note) documents
supported clients
as **mpv and Firefox only** — Chromium is never mentioned. Its design notes say
surfaces exported before their first decode (which is exactly how Chromium
probes formats) get a *throwaway* dma-buf backing that is dropped when the
surface binds to a real decode context, and that consumers are expected to
cache imports per surface id. Chromium sampling a stale empty backing yields
pure YUV(0,0,0) green with no logged error — matching every observation above.

1. **firefox-esr + the same driver** — most likely to work out of the box:
   `LIBVA_DRIVER_NAME=v4l2_request MOZ_DISABLE_RDD_SANDBOX=1` (the RDD sandbox
   blocks `/dev/video*`/`/dev/media*`) and `media.ffmpeg.vaapi.enabled=true`.
   Firefox has CPU-readback paths, so it displays even if GL import stays
   broken. Costs: slower browsing than Chromium on this device, sandbox off.
2. **Untried Chromium flags**: `--disable-gpu-compositing` (isolates GPU-side
   sampling from export/buffer mismatch) and `--use-angle=vulkan` (panvk
   imports dmabufs through a different stack; check the Mesa Vulkan ICD exists
   and watch RAM first).
3. **Confirm the stale-backing theory** with the driver's own trace
   (`v4l2r_trace`): watch whether the exported fd changes after the first
   decode while Chromium plays. If yes, that is a clean upstream issue.
4. **Repair the diagnostic consumers**: `ffmpeg -hwaccel vaapi` failed at
   device setup with `Cannot allocate memory` (CMA pressure) — retry with
   `cma=320M` or freed RAM to get a bit-exact `hwdownload` check independent
   of any browser.

Prepared offline 2026-10-17 while the device was offline: the driver (tag 1.3 then)
is cross-built in the qemu chroot by `tools/build-va-v4l2request.sh` (artifact
`work/va-driver/v4l2_request_drv_video.so`, arm64, NEEDED=libc only as VA
drivers require), and `tools/test-va-v4l2request.sh push|info|chromium|firefox`
runs the whole plan over SSH with screenshots pulled back to `work/va-shots/`.

### Revisit results (2026-10-17, device online)

- **Driver gate (`info`) passes**: vainfo under `LIBVA_DRIVER_NAME=v4l2_request`
  reports H264 CB/Main/High + HEVC Main/Main10 VLD via one Request API decoder.
- **Chromium matrix: still green in all three variants** (baseline,
  `--disable-gpu-compositing`, `--use-angle=vulkan`). Each run shows
  `decoding h264 via /dev/video0 [cedrus]` and the driver trace reports
  `bind wait … sync ≈0 ms` throughout — so decode completes and buffers bind
  cleanly; the green is Chromium *consuming* the wrong (stale/never-updated)
  backing, exactly the documented pre-first-decode export case. Not a sync bug.
- **firefox-esr 153 plays real frames — but software.** With
  `media.ffmpeg.vaapi.enabled=true` the PDM log still selects the plain FFmpeg
  decoder; strace shows libva + our driver *are* opened (GPU-process probe),
  yet the RDD decoder never initializes through them (zero driver-trace lines).
  Debian's ESR does not engage ffmpeg-vaapi in this environment out of the box.
- **Verdict (2026-10-17)**: browser VA display remains open; the green is
  Chromium consuming a stale backing.

### Chromium is fixed (2026-10-23)

The stale-backing theory was right, and upstream's current design (one CAPTURE
buffer per surface, queued with `V4L2_MEMORY_DMABUF`) is the fix: the surface's
memory is now allocated once and never swapped, so a client that imports it
before the first decode keeps sampling the right buffer. Evidence, from
instrumenting the driver while Chromium played a 1080p24 H.264 file:

- Chromium calls `vaExportSurfaceHandle()` **22 times at start-up** (its frame
  pool), before any frame has been decoded, then never again — it caches the
  EGL imports per surface id.
- On tag 1.3 those exports were throwaway standalone backings, dropped as soon
  as the decode context bound the surface to a CAPTURE buffer; Chromium kept
  sampling freed, zeroed memory: YUV(0,0,0), flat green, forever. (Instrumenting
  `vaDeriveImage` on the other entry point showed the same: 22/22 derivations
  with `bound=0` and `ysum=0`.)
- On master + the single-planar port there is no swap and no copy; the picture
  is correct, subtitles included, with no Chromium flags at all beyond the
  session's `LIBVA_DRIVER_NAME=v4l2_request`, at 154–174 % of one core and
  ~1.0 GB RSS
  (software: 251–260 %, 887–1051 MB, three 10 s runs). The gain is modest
  because a browser's own work — layout, compositing, subtitle rendering —
  dominates; the video decode is no longer part of it.
- Firefox still does not engage its VA-API decoder here, so it stays software.

An intermediate revision (tag 1.3 plus a "keep the backing and copy every frame
into it" fix) also un-greened Chromium, at one NV12 copy per frame; it was
dropped when the base moved to master, which solves it structurally.

## Watching video with VLC (3.0.24, XWayland, zero-copy)

VLC has no V4L2 path of its own, but it speaks VA-API, and the libva driver over
the request API (`tools/build-va-v4l2request.sh`, upstream master + the
single-planar port) reaches Cedrus. With the interop fixes described below it
decodes **and displays zero-copy** through EGL + `glconv_vaapi_x11`:

```
$ LIBVA_DRIVER_NAME=v4l2_request vlc --avcodec-hw=vaapi file.mkv
[avcodec] Using v4l2-request for hardware decoding
libva-v4l2request: decoding h264 via /dev/video0 [cedrus] (media /dev/media0)
[egl_x11] using opengl module "egl_x11"
[generic] using glconv module "glconv_vaapi_x11"
```

Measured 2026-10-23 on the device, 1080p24 sources, CPU from `/proc/<pid>/stat`
over 8 s (1440×1080 HEVC source is a 6 s clip, looped):

| VLC 3.0.24 | CPU (one core) | VLC software, same file |
|---|---|---|
| H.264 1080p | 11 % | 208 % |
| HEVC 1080p | 22 % | 207 % |
| HEVC 540p | 13 % | 81 % |

mpv is 18 % on the H.264 file (its `vo=gpu` does more work than VLC's bare GL
surface), so VLC is not the slow path any more. Zero dropped frames, no late
pictures in either codec. The full picture, including RAM, GPU and battery, is
in "Player resource matrix" below.

Quirks worth knowing:

- **XWayland only.** VLC 3.0's Wayland window modules speak `wl_shell` and the
  pre-stable xdg-shell; labwc offers neither (`main window debug: no vout window
  modules matched`), so VLC needs `DISPLAY=:0`. VLC 4 has stable xdg-shell but is
  not in trixie.
- **No per-app flags.** VLC's default `avcodec-hw=any` picks VA-API once a VA
  driver answers, and the default vout lands on `gl` + `egl_x11` + the vaapi
  converter by itself. The only thing that has to be in the environment is
  `LIBVA_DRIVER_NAME=v4l2_request`; the desktop session sets it (see "Default
  on" below). Without it VLC decodes in software (227 %) and says nothing.
- `--vout=xcb_x11` is the copy fallback (VAOP→I420 via `vaapi_filters`, 94 %
  CPU): slower, but it needs no dmabuf interop, so keep it as a diagnosis tool.

### The driver fixes (`build/patches/libva-v4l2-request-fixes.patch`, on master)

1. **`vaAcquireBufferHandle()`/`vaReleaseBufferHandle()` were stubs** returning
   `VA_STATUS_ERROR_UNIMPLEMENTED`. VLC 3 probes its dmabuf path before it
   accepts the GL converter (`vaDeriveImage`, then Acquire with DRM_PRIME, then
   an EGLImage in `tc_vaegl_get_pool`); the probe failing aborted the whole vout
   and VLC fell back to software decoding without an error. The patch hands out
   the dma-buf `vaExportSurfaceHandle()` would return, dup'ed per image.
2. **With that fixed VLC drew a uniform green window.** Not a bad import: the
   driver exported a composite descriptor (one layer, `num_planes = 2`) because
   VLC passes `flags = 0`, and VLC 3 *rejects* any multi-plane layer in its GL
   converter (`if (layers[i].num_planes > 1) goto error;`) — an empty GL surface
   reads as YUV(0,0,0), which converts to flat green. `VA_EXPORT_SURFACE_SEPARATE_LAYERS`
   is a hint rather than a requirement, so the patch now always exports NV12/P010
   as two single-plane layers (R8 + GR88) pointing into the same object.
   Verified by dumping the exported buffer from inside the driver: it held real
   decoded luma (`ysum` ≈ 1.2 M, non-zero across the plane) while the screen was
   green, which is what ruled out a wrong plane offset or modifier.

3. **Single-planar support** (the only non-VA fix, and the reason the base is
   master + patch rather than master as-is). Master's commit `4cb4bde`
   ("require multiplane support") deleted the dual-planar plumbing
   (−183/+69 lines) because its author's SoCs are multiplanar; cedrus exposes
   `V4L2_CAP_VIDEO_M2M` only, so the probe fails with `no V4L2 Request API
   decoder found` and neither VLC nor Chromium ever reaches the VPU. The patch
   restores the fallback in one place (format accessors + the buffer type
   choice) instead of reverting that commit.

**Why not convert cedrus to multiplanar instead?** It would let us run upstream
unmodified, but it is a ~300–400 line change to a shared kernel interface
(`ctx->src_fmt/dst_fmt` is referenced 46 times across `cedrus_video.c`,
`cedrus_dec.c` and the three codec backends, plus the vb2 queue types and
`queue_setup`), it would have to be re-validated for *every* consumer —
Moonlight's own FFmpeg, system ffmpeg/mpv, VLC, Chromium — and re-applied on
each ROCKNIX kernel bump. Fixing the component that made the assumption (the
libva driver, which is SoC-generic by design) has a far smaller blast radius.
This single-planar patch is also the piece worth sending upstream.

## Player resource matrix (measured 2026-10-23)

All rows are with the shipped driver build (upstream master + single-planar
port) and VLC 3.0.24. `tools/bench-video-players.py` loops a 1080p24 H.264 file,
skips the first 7 s, then samples for 12 s: CPU is process-tree ticks over that
window (one core = 100 %), RAM is tree `VmRSS`, GPU is the Mali devfreq
frequency 4×/s (governor is `simple_ondemand`, so frequency tracks load) and
battery is the AXP20x `current_now`. The panel is 640×480, so only the video
decode/upload differs between rows.

| configuration | decode | display | CPU (1 core) | RAM | GPU | picture |
|---|---|---|---|---|---|---|
| mpv `hwdec=auto-safe` | VPU (`drm`) | dmabuf→GL, zero-copy | **18 %** | 129 MB | 420 MHz (idle) | correct |
| mpv `hwdec=v4l2request-copy` | VPU | CPU download | 114 % | 144 MB | 420 MHz | correct |
| mpv `hwdec=no` | CPU | — | 152 % | 186 MB | 420 MHz | correct |
| VLC `--avcodec-hw=vaapi` | VPU (VA-API) | dmabuf→EGL, zero-copy | **11 %** | 142 MB | 458 MHz (17 % at 648) | correct |
| VLC `--vout=xcb_x11` | VPU | VAOP→I420 copy | 93 % | 85 MB | 420 MHz | correct |
| VLC `--avcodec-hw=none` | CPU | — | 227 % | 241 MB | 420 MHz | correct |
| `ffmpeg -hwaccel v4l2request -f null` | VPU | none, frames downloaded | 104 % | 77 MB | — | 27 fps (1.12×) |
| `ffmpeg -f null` | CPU | none | 373 % | 102 MB | — | 57 fps (2.39×) |
| Chromium (default) | CPU | — | 251–260 % | 887–1051 MB | 420 MHz | correct |
| Chromium + `LIBVA_DRIVER_NAME=v4l2_request` | VPU (VA-API) | dmabuf→GL | 154–174 % | ~1003 MB | 420 MHz | correct |

HEVC (6 s clips, looped):

| configuration | CPU (one core) | software, same file |
|---|---|---|
| VLC zero-copy, HEVC 1080p | **22 %** | 207 % |
| VLC zero-copy, HEVC 540p | **13 %** | 81 % |
| mpv zero-copy, HEVC 1080p (120-frame runs, earlier) | ~75 % at 36 fps | ~266 % |

What the numbers say:

- **The GPU is not the bottleneck at this panel size.** Mali stayed at its
  minimum 420 MHz in every run (VLC zero-copy occasionally 430–477 MHz, ≤4 % of
  samples at 648 MHz), including Chromium's software path. Playback here is
  CPU/VPU-bound; the GPU only composites 640×480.
- **Battery draw cannot separate the paths.** `current_now` read 416–427 mA in
  all ten scenarios, software decode at 376 % CPU included — the AXP2202 gauge
  on this board is as broken as `docs/power-and-sleep.md` records. CPU time is
  the only usable energy proxy, and by it the zero-copy paths (11–20 %) are in a
  different class from anything software (152–376 %).
- **The VPU is cheaper, not faster.** Decode-only ffmpeg is *slower* on hardware
  than on the CPU (27 vs 57 fps): the win is 3–4× less CPU, which buys real-time
  playback with audio, subtitles and thermal headroom. Do not expect a higher
  decode rate.
- **VLC now beats mpv on CPU** (11 % vs 20 %) because its GL surface does less
  work than `vo=gpu`; mpv remains the better player (subtitles, OSD,
  `vo=dmabuf-wayland`, no XWayland requirement).
- **Chromium is the odd one out**: it is the only listed configuration that
  burns a core *and* the only one with RAM near 1 GB, and the VPU buys it only
  ~1.5× CPU rather than 10×, because a browser's own work (layout, compositing,
  subtitle rendering) dominates once decode is off the CPU. It is also the only
  row measured over three runs: the browser moves the number by tens of percent.
- **The numbers are single runs unless a range is given** (`/proc` sampling is
  stable for the players; the browser is not).


### Upstream status (checked 2026-10-23)

- `sofus13/libva-v4l2_request`: the pin (`f54d8d2`, 2026-10-20) **is** current
  master; nothing newer. Upstream diagnosed and fixed the same Chromium green
  we hit — issues #1 "decode into surfaces the client exported before the first
  decode", #2 "Fix green Chromium video from early surface export" and #5
  "Decode into the client's exported buffer" are closed by the per-surface
  buffer design we now build on. Issue #6 (surface contents after
  `vaDestroyContext`) is still open, though the cleanup in master only detaches
  and no longer frees a live surface's buffer.
- cedrus (linux-media patchwork): nothing pending that affects the H700. The
  H616 variant we use was accepted (v3 4/7, 2026-07-12); the probe-cleanup and
  control-handler leak fixes (accepted 2026-04/06) are already in our 7.2 tree
  (`v4l2_ctrl_handler_free` / `media_device_unregister` in the error paths).
  In flight: a series switching the SRAM/reserved-memory setup to
  `devm_of_reserved_mem_device_init()` (v2 6/6, 2026-09-02) — if it lands it may
  change what the DT node has to describe, so re-check our overlay when bumping
  the kernel. A VP9 backend for cedrus does exist outside mainline (Jernej
  Skrabec's series, taken from LibreELEC's Allwinner patch set, listed with
  provenance in `build/kernel/libreelec/README.md`) and this image ships it;
  AV1 is not in the silicon.
- VLC: trixie ships 3.0.23 (3.0.24 in proposed-updates/sid); there is no VLC 4
  package, so VLC's Wayland-window limitation (and the XWayland requirement
  above) stands until a newer VLC is packaged.

## Default on

Two pieces put Chromium and VLC on the VPU without per-app flags:

- `build/04e-va-api.sh` ships the driver (`/usr/lib/aarch64-linux-gnu/dri/v4l2_request_drv_video.so`),
  built and patched by `tools/build-va-v4l2request.sh`.
- `overlay/etc/profile.d/zz-rg35xxh-session.sh` exports
  `LIBVA_DRIVER_NAME=v4l2_request` before `exec labwc`, so every app started
  from the desktop inherits it. Nothing else is needed: VLC's default
  `avcodec-hw=any` selects VA-API, Chromium enables `VaapiVideoDecoder` on its
  own.

Why the variable and not "just work": libva has no config file and no usable
built-in default driver on arm64 — the driver name is chosen by
`LIBVA_DRIVER_NAME` or a compiled-in default that does not exist here. If the
variable is unset, or the `.so` is missing, `vaInitialize` fails and both apps
fall back to software decode (no green, no crash) — that is also the switch to
turn it off (`unset LIBVA_DRIVER_NAME`, or drop the overlay line).

Caveat: the variable is exported for the whole session, so any other VA-API
consumer inherits it. On this image that is only `ffmpeg -hwaccel vaapi`
(uselessly memory-hungry here: `Cannot allocate memory` at device setup under
CMA pressure) and Firefox (does not engage its VA decoder anyway).

## Watching streams (YouTube, Twitch, …)

`goblin-watch <url>` plays a stream on the VPU: `yt-dlp` (installed by
`build/04f-streaming.sh`, `pipx install --global`) extracts, `mpv` plays and
decodes with Cedrus.

```
$ goblin-watch https://www.youtube.com/watch?v=…
 ● Video  --vid=1  (h264 1280x720 60 fps) [default]
 Using hardware decoding (drm).
 VO: [gpu] 1280x720 drm_prime[nv12]
```

The wrapper pins three things: `--ytdl-format` prefers **H.264** (the only
codec Cedrus decodes; YouTube otherwise serves VP9/AV1, which would fall back to
software), caps at **720p** (the panel is 640×480), and passes
`--ytdl-raw-options=js-runtimes=node` — yt-dlp needs a JavaScript runtime for
YouTube and `nodejs` already ships in the image.

Measured 2026-10-23, 720p60 H.264 from YouTube: **47 % of one core, 144 MB RSS**,
zero-copy (`drm_prime[nv12]`). One transient
`Error while decoding frame (hardware decoding)!` appears on the first frame;
playback continues on hardware.

Why not a browser: the same video in Chromium is 154–174 % CPU and ~1 GB RSS on
a 975 MB device. Why not VLC: YouTube only offers DASH (separate video and audio
URLs, no progressive format left), and VLC cannot mux two URLs; mpv can. VLC is
fine for Twitch, whose HLS is already muxed H.264+AAC.

yt-dlp goes stale when YouTube changes: update with
`pipx upgrade --global yt-dlp` on the device (or rebuild with a newer
`YTDLP_VERSION`). The Debian package (2025.04) is already too old and fails with
`The page needs to be reloaded`.

## How it works

| Piece | What | Where |
|---|---|---|
| Decoder hardware | Allwinner Cedar video engine (same as H6): MPEG-2, H.264, H.265 8/10-bit, VP8, and VP9 8-bit through its own backend (out-of-tree series, shares the H.265 engine slot). No AV1 (not in hardware). | `video-codec@1c0e000` |
| Kernel driver | Cedrus, V4L2 **stateless** (request API) → `/dev/video0`, `/dev/media0` | `sunxi-cedrus.ko` in `/usr/lib/modules/7.2.0/extra/`, loaded automatically from the DT node; our patch gives the decoded picture a 64-byte aligned stride, which is what the GPU needs to import it (see "The blue video") |
| Device tree | ROCKNIX DTB + overlay adding the video-engine node | `/boot/firmware/dtb.img` (original kept as `dtb-rocknix.img`) |
| Memory | Decoder buffers come from CMA: `cma=256M` on the kernel command line (ROCKNIX default is 32 MB). Unused CMA stays available to normal programs. 1080p streaming uses ~140 MB. | `extlinux/extlinux.conf` |
| Heap access | dma-buf heaps are `root:root 0600` in the kernel; the overlay's `72-rg35xxh-dma-heap.rules` gives group `video` access, otherwise ffmpeg logs `Unable to open any dma_heap device` and no dmabuf path can allocate. | `overlay/etc/udev/rules.d/` |
| Userspace | `build/04c-v4l2-ffmpeg.sh` installs Kwiboo's FFmpeg (`v4l2request` hwdevice + per-codec hwaccels) over the Debian libs, with the same external libraries the distro build has (gnutls for https, x264/lame/opus/vorbis/vpx encoders, libass for subtitles, dav1d for AV1); the replaced `libav*` packages are held with `apt-mark` so an upgrade cannot overwrite them. `/etc/mpv/mpv.conf` sets `hwdec=auto-safe`, which lands on zero-copy `drm`, and `hwdec-codecs=h264,hevc,mpeg2video,vp8`. Moonlight uses its own bundled FFmpeg. | `build/`, `overlay/etc/mpv/` |

Players:

- **Moonlight** — zero-copy, 1080p60 HEVC works today; nothing to install.
- **mpv / ffmpeg (system)** — hardware decode works, zero-copy by default
  (`hwdec=auto-safe` → `drm` in `/etc/mpv/mpv.conf`), copy paths as fallback
  (`v4l2request-copy`, `drm-copy`), and `ffmpeg -hwaccel v4l2request` on the CLI.
  Throughput caveats above. AV1 is software (dav1d) on purpose: no Cedrus AV1.
- **VLC 3.0.24** — zero-copy through the libva bridge (see "Watching video with
  VLC"): `LIBVA_DRIVER_NAME=v4l2_request vlc --avcodec-hw=vaapi`, under XWayland.
- Not covered: ffplay decodes in software only, and Chromium cannot use the V4L2
  stateless decoder (its Linux decoder only offers the GL output path, which does
  not accept these dmabufs).

## Source

Upstream series "[PATCH v3 0/7] arm64: allwinner: h616: Support Video Engine" (Chen-Yu Tsai, 2026-07-12; reviewed by Jernej Škrabec, DT acked by Rob Herring; DT patches applied to `sunxi/dt-for-7.4` on 2026-10-05). We use:

- **Patch 4/7** (driver, 4 lines): H616 compatible → existing H6 variant. `build/kernel/0001-cedrus-add-h616-variant.patch`.
- **Patch 7/7** (DT node): as an overlay, `build/dts/rg35xxh-video-engine.dtso`, **without the `iommus` property** (see below).

On top of those, one patch of our own on the driver:
`build/kernel/0002-cedrus-64-byte-stride.patch` — the capture stride is
aligned to 64 bytes instead of 16, and the VPU's framebuffer line stride
register is programmed from the negotiated `bytesperline`. Without it the
GPU cannot import the decoded picture (see "The blue video").

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

Without the VPU, `hwdec=auto-safe` falls back to software automatically
(`--hwdec-software-fallback` defaults to yes) — but note the pre-existing Mesa
crash on that path above; `vo=gpu-next` is worse, not better.

## Display caveat

The decoder claims SRAM C, which the 7.2 source says is toggled together with the display engine's region. No display problems were seen while streaming 1080p, but watch for glitches.
