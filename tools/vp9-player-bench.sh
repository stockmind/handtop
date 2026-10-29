#!/bin/bash
# VP9 1080p player benchmark: software vs copy vs zero-copy (drmprime).
# --untimed + fixed frame count: fps is throughput; CPU comes from bash's
# `time -p` for that single run (share of one core = (user+sys)/real).
export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0
F="$HOME/test-media/vp9-1080p.mkv"
FRAMES=240

run() {
	local name=$1; shift
	pkill -x mpv; sleep 1
	{ time -p mpv "$@" --hwdec-codecs=h264,hevc,mpeg2video,vp8,vp9 \
		--no-audio --untimed --really-quiet --msg-level=all=info \
		--frames=$FRAMES "$F" > /tmp/vp9-$name.log 2>&1 ; } 2> /tmp/vp9-$name.time
	local rc=$?
	local real=$(awk '/^real/{print $2}' /tmp/vp9-$name.time)
	local user=$(awk '/^user/{print $2}' /tmp/vp9-$name.time)
	local sys=$(awk '/^sys/{print $2}' /tmp/vp9-$name.time)
	local dec=sw
	grep -q "Using hardware decoding (drm" /tmp/vp9-$name.log && dec=zero
	grep -q "Using hardware decoding (v4l2request-copy" /tmp/vp9-$name.log && dec=copy
	if [ $rc -ne 0 ] || grep -q "Could not initialize video chain" /tmp/vp9-$name.log; then
		printf "  %-10s FAILED (rc=%s)\n" "$name" "$rc"; return
	fi
	printf "  %-10s %-4s %6.1f fps  %5.0f%% of one core\n" "$name" "$dec" \
		"$(awk -v f=$FRAMES -v r=$real 'BEGIN{print f/r}')" \
		"$(awk -v u=$user -v s=$sys -v r=$real 'BEGIN{print (u+s)/r*100}')"
}

pkill -x mpv
run sw   --hwdec=no --vo=gpu --gpu-context=wayland
run copy --hwdec=v4l2request-copy --vo=gpu --gpu-context=wayland
run zero --hwdec=drm --vo=gpu --gpu-context=wayland
pkill -x mpv
