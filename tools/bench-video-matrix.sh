#!/bin/bash
# Decode matrix on the 90 s Jellyfin-sourced clips in ~/test-media/bench.
# Methods: ffmpeg -benchmark to null (decode only, ms/frame and fps), mpv
# --frames=240 --untimed (throughput, ms/frame and % of one core at 24 fps),
# browsers: 25 s settle + 12 s CPU sample of the whole process tree.
export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0
export LIBVA_DRIVER_NAME=v4l2_request
HZ=$(getconf CLK_TCK)
cd "$HOME/test-media/bench" || exit 1
HL="h264,hevc,mpeg2video,vp8,vp9"

ffrun() { # extra-args...
	local out frames u s r
	out=$(ffmpeg -nostdin -hide_banner -loglevel info -benchmark "$@" -t 30 -f null - 2>&1)
	frames=$(grep -oE 'frame= *[0-9]+' <<<"$out" | tail -1 | grep -oE '[0-9]+')
	u=$(grep -oE 'utime=[0-9.]+' <<<"$out" | cut -d= -f2)
	s=$(grep -oE 'stime=[0-9.]+' <<<"$out" | cut -d= -f2)
	r=$(grep -oE 'rtime=[0-9.]+' <<<"$out" | cut -d= -f2)
	if [ -z "$frames" ]; then echo "  n/a"; return; fi
	awk -v f="$frames" -v u="$u" -v s="$s" -v r="$r" \
		'BEGIN{printf "%6.1f ms/f  %5.0f fps", (u+s)*1000/f, f/r}'
}

mpvrun() { # vo
	local t u s
	t=$( { time -p mpv --no-config --hwdec=drm --hwdec-codecs=$HL --no-audio \
		--frames=240 --untimed --really-quiet --vo="$1" \
		--gpu-context=wayland *.mkv 2>/dev/null ; } 2>&1 )
	u=$(awk '/^user/{print $2}' <<<"$t"); s=$(awk '/^sys/{print $2}' <<<"$t")
	awk -v u="$u" -v s="$s" 'BEGIN{printf "%6.1f ms/f  %4.0f%% @24fps", (u+s)*1000/240, (u+s)*10}'
}

printf "%-16s %-22s %-22s %-22s %-22s\n" file "ffmpeg hw->null" "ffmpeg sw->null" "mpv dmabuf-wayland" "mpv gpu"
for f in h264-1080.mkv hevc-1080.mkv hevc-720p10.mkv vp9-1080.mkv vp9-720p10.mkv vp8-720.mkv mpeg2-1080.mkv; do
	printf "%-16s %-22s %-22s %-22s %-22s\n" "$f" \
		"$(ffrun -hwaccel v4l2request -i "$f")" \
		"$(ffrun -i "$f")" \
		"$(set -- dmabuf-wayland; t=$( { time -p mpv --no-config --hwdec=drm --hwdec-codecs=$HL --no-audio --frames=240 --untimed --really-quiet --vo=dmabuf-wayland --gpu-context=wayland "$f" >/dev/null 2>&1; } 2>&1 ); u=$(awk '/^user/{print $2}' <<<"$t"); s=$(awk '/^sys/{print $2}' <<<"$t"); awk -v u="$u" -v s="$s" 'BEGIN{printf "%6.1f ms/f  %4.0f%% @24fps", (u+s)*1000/240, (u+s)*10}')" \
		"$(t=$( { time -p mpv --no-config --hwdec=drm --hwdec-codecs=$HL --no-audio --frames=240 --untimed --really-quiet --vo=gpu --gpu-context=wayland "$f" >/dev/null 2>&1; } 2>&1 ); u=$(awk '/^user/{print $2}' <<<"$t"); s=$(awk '/^sys/{print $2}' <<<"$t"); awk -v u="$u" -v s="$s" 'BEGIN{printf "%6.1f ms/f  %4.0f%% @24fps", (u+s)*1000/240, (u+s)*10}')"
done

browser() { # label file cmd...
	local label=$1 f=$2; shift 2
	pkill -f chromium 2>/dev/null; pkill -f firefox-esr 2>/dev/null; sleep 3
	setsid "$@" "file://$PWD/$f" >/tmp/bx-$label.log 2>&1 &
	sleep 25
	cpu() { for p in $(pgrep -f "$3"); do awk '{print $14+$15}' /proc/$p/stat 2>/dev/null; done | paste -sd+ | bc; }
	t0=$(cpu); sleep 12; t1=$(cpu)
	printf "  %-24s %3s%% of one core   vpu=%s\n" "$label" \
		"$(( (t1-t0)*100/HZ/12 ))" "$(grep -ac 'via /dev/video0' /tmp/bx-$label.log)"
	pkill -f "$3"
}

echo
echo "browsers (25 s settle, 12 s sample, file://)"
browser chromium-h264 h264-1080.mkv chromium --no-default-browser-check --autoplay-policy=no-user-gesture-required --start-fullscreen
browser chromium-vp9 vp9-1080.mkv chromium --no-default-browser-check --autoplay-policy=no-user-gesture-required --start-fullscreen
browser firefox-h264 h264-1080.mkv firefox-esr --kiosk
browser firefox-vp9 vp9-1080.mkv firefox-esr --kiosk
