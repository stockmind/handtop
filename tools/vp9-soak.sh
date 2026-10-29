#!/bin/bash
# Soak VP9 playback on the handheld and record what the earlier H.264 soak
# recorded: battery rail, CMA, swap, decoder RSS, CPU, and whether the player
# survived. Run on the device:
#
#   tools/vp9-soak.sh [minutes] [file] [mpv args...]
#
# Defaults: 10 minutes, ~/test-media/vp9-1080p.mkv, shipped mpv.conf.
# Samples every 5 s; prints a summary at the end and leaves the log in
# ~/vp9-soak.log so a failure can be inspected afterwards.
set -u
MIN=${1:-10}; shift || true
FILE=${1:-$HOME/test-media/vp9-1080p.mkv}; shift || true

export XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0
LOG=$HOME/vp9-soak.log
HZ=$(getconf CLK_TCK)
SAMPLES=$(( MIN * 12 ))

# Battery supply: whatever exposes voltage_now (bat0 on this image).
PS=""
for d in /sys/class/power_supply/*/; do
	[ -r "$d/voltage_now" ] && { PS=$d; break; }
done

pkill -x mpv; sleep 1
setsid mpv "$@" --loop --really-quiet "$FILE" > /tmp/soak-mpv.log 2>&1 &
pid=$!
start=$(date +%s)
prev=$(awk '{print $14+$15}' /proc/$pid/stat 2>/dev/null || echo 0)

: > "$LOG"
echo "# n rail_uV cur_uA cmafree_kb swapfree_kb ticks rss_kb alive" >> "$LOG"
for i in $(seq 1 "$SAMPLES"); do
	sleep 5
	rail=$(cat "$PS/voltage_now" 2>/dev/null || echo 0)
	cur=$(cat "$PS/current_now" 2>/dev/null || echo 0)
	cma=$(awk '/^CmaFree:/{print $2}' /proc/meminfo)
	swapf=$(awk '/^SwapFree:/{print $2}' /proc/meminfo)
	ticks=$(awk '{print $14+$15}' /proc/$pid/stat 2>/dev/null || echo "$prev")
	rss=$(awk '/VmRSS/{print $2}' /proc/$pid/status 2>/dev/null || echo 0)
	alive=1; kill -0 "$pid" 2>/dev/null || alive=0
	echo "$i $rail $cur $cma $swapf $ticks $rss $alive" >> "$LOG"
	[ "$alive" = 1 ] || break
done
end=$(date +%s)
last=$(awk '{print $14+$15}' /proc/$pid/stat 2>/dev/null || echo "$prev")
alive=1; kill -0 "$pid" 2>/dev/null || alive=0
pkill -x mpv

{
	echo "file=$FILE args=$*"
	echo "elapsed=$((end-start))s mpv_alive_at_end=$alive"
	echo "avg_cpu=$(( (last-prev)*100/HZ/(end-start) ))% of one core"
	echo "samples=$(($(wc -l < "$LOG") - 1)) alive_samples=$(awk 'NR>1{a+=$8} END{print a}' "$LOG")"
	echo "cma_free_min_kb=$(awk 'NR>1{if(!m||$4<m)m=$4} END{print m}' "$LOG")"
	echo "swap_free_min_kb=$(awk 'NR>1{if(!m||$5<m)m=$5} END{print m}' "$LOG")"
	echo "rss_max_kb=$(awk 'NR>1{if($7>m)m=$7} END{print m}' "$LOG")"
	echo "rail_min_uV=$(awk 'NR>1{if(!m||$2<m)m=$2} END{print m}' "$LOG")"
	echo "rail_max_uV=$(awk 'NR>1{if($2>m)m=$2} END{print m}' "$LOG")"
	echo "power_mW_avg=$(awk 'NR>1 && $2>0 && $3>0 {s+=$2*$3; n++} END{if(n) printf "%.0f", s/n/1000000000; else print "n/a"}' "$LOG")"
	echo "mpv_error_lines=$(grep -ciE 'error|fail' /tmp/soak-mpv.log)"
	echo "dmesg_cedrus_lines=$(dmesg 2>/dev/null | grep -ci cedrus)"
} | tee -a "$LOG"
