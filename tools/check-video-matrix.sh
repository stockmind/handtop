#!/bin/bash
# VP9 + H.265 + H.264 across formats/widths against a software decode.
SUDO() { echo rg35xxhh | sudo -S -p '' "$@"; }
SUDO install -D -m644 /home/rg/cedrus-h265p010.ko /lib/modules/7.2.0/extra/sunxi-cedrus.ko
SUDO depmod -a 7.2.0; SUDO modprobe -r sunxi_cedrus; SUDO modprobe sunxi_cedrus; sleep 1
cd "$HOME" || exit 1
run() { # file pixfmt
	local f=$1 pf=$2
	local wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$f")
	rm -f a.yuv b.yuv
	timeout 60 ffmpeg -nostdin -hide_banner -loglevel error -hwaccel v4l2request -i "$f" -frames:v 5 -pix_fmt $pf -f rawvideo a.yuv -y 2>/dev/null
	timeout 60 ffmpeg -nostdin -hide_banner -loglevel error -i "$f" -frames:v 5 -pix_fmt $pf -f rawvideo b.yuv -y 2>/dev/null
	local p=$(ffmpeg -nostdin -hide_banner -f rawvideo -pix_fmt $pf -s $wh -i a.yuv -f rawvideo -pix_fmt $pf -s $wh -i b.yuv -lavfi psnr -f null - 2>&1 | grep -o 'average:[^ ]*' | head -1)
	printf "  %-22s %-10s %-6s %s\n" "$(basename $f)" "$wh" "$pf" "${p:-no psnr}"
}
run test-media/hevc-1080.mp4 nv12
run test-media/hevc-720p10.mp4 p010le
run Downloads/media/hevc-960x540.mp4 nv12
run test-media/h264-1080.mp4 nv12
run test-media/h264-854.mp4 nv12
run test-media/vp9-1280-720.mkv nv12 2>/dev/null
run test-media/vp9-720p.mkv nv12
run test-media/vp9-854x480.mkv nv12
run test-media/vp9-1366x768.mkv nv12
run test-media/vp9-1080p.mkv nv12
run test-media/vp9-4k.mkv nv12
run test-media/vp9-720p10.mkv p010le
