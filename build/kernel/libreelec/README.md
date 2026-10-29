# Third-party sources used by this fork

Everything here was picked up from somewhere else. Keep this file honest: when
something is lifted from an external tree, list the origin, the author and the
date it was fetched, and say what we changed.

## VP9 for cedrus (H616/H700)

Origin: LibreELEC.tv, `projects/Allwinner/patches/linux/`
(repo <https://github.com/LibreELEC/LibreELEC.tv>, branch `master`).
Found through a code search for `cedrus_vp9`
(<https://grep.app/search?q=cedrus_vp9>).
Fetched 2026-10-29 from
`https://raw.githubusercontent.com/LibreELEC/LibreELEC.tv/master/projects/Allwinner/patches/linux/<file>`.

Author of the series: Jernej Skrabec <jernej.skrabec@gmail.com> (the current
cedrus maintainer). The patches carry his `Signed-off-by` and are labelled
`[PATCH nnn/419]` against their 7.2 rebase, which matches the ROCKNIX 7.2
kernel we build against. GPL-2.0, same license as the driver.

| file | what it does | used |
|---|---|---|
| 0410-media-cedrus-Don-t-CPU-map-source-buffers.patch | `DMA_ATTR_NO_KERNEL_MAPPING` on the output queue | yes |
| 0411-media-cedrus-Add-VP9-decoding-support.patch | the whole VP9 backend (`cedrus_vp9.c`, 1297 lines) | yes |
| 0421-media-cedrus-Select-V4L2_VP9-for-the-VP9-helpers.patch | `select V4L2_VP9` in Kconfig | yes |
| 0412-media-cedrus-Add-P010-capture-format-and-shared-10-b.patch | P010 capture + shared 10-bit handling | for 10-bit, not yet |
| 0413-media-cedrus-Add-VP9-P010-output-support.patch | VP9 P010 output | for 10-bit, not yet |
| 0415-media-cedrus-Name-H616-VP9-mode-register-bits.patch | names the VP9 mode bits | not yet |
| 0417/0418 | format filtering by bit depth | for 10-bit, not yet |
| 0424-arm64-dts-allwinner-sun50i-h616-Add-video-engine.patch | H616 VE devicetree node | not needed (ROCKNIX DTS already has it) |

How they are applied: `build/06b-cedrus.sh` applies `build/kernel/*.patch` on
top of the ROCKNIX tree; these are applied by hand on top of that (see
`docs/vp9-plan.md`, "Module build loop"), because 0411 supersedes our own
`0003-cedrus-vp9.patch` experiment. Our earlier hand-rolled VP9 plumbing
(M0/M1 and the parameter-block fill) is kept in that patch file only as
history; it is not part of the build once 0411 is in.

What we changed on top: nothing in the code. Only the build plumbing (which
patches are applied) and the documentation are ours.
