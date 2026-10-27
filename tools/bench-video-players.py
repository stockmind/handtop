#!/usr/bin/env python3
"""Measure CPU, RAM, GPU and battery draw of every video path on the device.

Runs *on* the device (it reads /proc, the Mali devfreq and the AXP gauge) and
prints one JSON object per scenario, optionally a markdown table:

    scp tools/bench-video-players.py goblin:/tmp/
    ssh goblin 'python3 /tmp/bench-video-players.py --markdown'

Method: start the player, wait --warm seconds (start-up, pool allocation, the
first slow frames), then sample for --seconds; CPU is process-tree ticks over
that window (one core = 100 %), RAM is tree VmRSS, GPU is the Mali devfreq
frequency sampled 4x/s (the governor is simple_ondemand, so it tracks load),
battery is the AXP20x current_now, which is useless on this board (it reports
~420 mA whatever is running) - kept only to show that.

Numbers from the 2026-10-23 run are in docs/video-decode.md.
"""
import argparse, json, os, signal, statistics, subprocess, sys, time

HZ = os.sysconf("SC_CLK_TCK")
NPROC = os.sysconf("SC_NPROCESSORS_ONLN")
DEVFREQ = "/sys/class/devfreq/1800000.gpu"
ENV = dict(os.environ, XDG_RUNTIME_DIR="/run/user/1000",
           WAYLAND_DISPLAY="wayland-0", DISPLAY=":0")


def scenarios(media):
    """Each entry: (name, command, needs the VA driver env)."""
    va = ["env", "LIBVA_DRIVER_NAME=v4l2_request"]
    url = "file://" + media
    return [
        ("mpv-hw-zerocopy",
         ["mpv", "--no-audio", "--hwdec=auto-safe", "--vo=gpu",
          "--profile=fast", "--loop", media], False),
        ("mpv-hw-copy",
         ["mpv", "--no-audio", "--hwdec=v4l2request-copy", "--vo=gpu",
          "--profile=fast", "--loop", media], False),
        ("mpv-sw",
         ["mpv", "--no-audio", "--hwdec=no", "--vo=gpu",
          "--profile=fast", "--loop", media], False),
        ("vlc-hw-zerocopy",
         va + ["vlc", "-I", "dummy", "--no-audio", "--loop",
               "--avcodec-hw=vaapi", media], True),
        ("vlc-hw-copy",
         va + ["vlc", "-I", "dummy", "--no-audio", "--loop", "--vout=xcb_x11",
               "--avcodec-hw=vaapi", media], True),
        ("vlc-sw",
         ["vlc", "-I", "dummy", "--no-audio", "--loop",
          "--avcodec-hw=none", media], False),
        ("ffmpeg-hw",
         ["ffmpeg", "-nostdin", "-hwaccel", "v4l2request", "-i", media,
          "-f", "null", "-"], False),
        ("ffmpeg-sw",
         ["ffmpeg", "-nostdin", "-i", media, "-f", "null", "-"], False),
        ("chromium-sw",
         ["chromium", "--kiosk", "--autoplay-policy=no-user-gesture-required",
          "--ozone-platform=wayland", url], False),
        ("chromium-hw",
         va + ["chromium", "--kiosk",
               "--autoplay-policy=no-user-gesture-required",
               "--ozone-platform=wayland", url], True),
    ]


def tree(pgid):
    pids = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            fields = open(f"/proc/{entry}/stat").read().rsplit(") ", 1)[1].split()
            if int(fields[2]) == pgid:
                pids.append(int(entry))
        except (OSError, IndexError, ValueError):
            pass
    return pids


def sample(pgid):
    ticks = rss = 0
    for pid in tree(pgid):
        try:
            st = open(f"/proc/{pid}/stat").read().rsplit(") ", 1)[1].split()
            ticks += int(st[11]) + int(st[12])
            for line in open(f"/proc/{pid}/status"):
                if line.startswith("VmRSS:"):
                    rss += int(line.split()[1]) // 1024
        except OSError:
            pass
    return ticks, rss


def gpu_max_mhz():
    try:
        return int(open(f"{DEVFREQ}/max_freq").read()) // 1_000_000
    except OSError:
        return 0


def gpu_mhz():
    try:
        return int(open(f"{DEVFREQ}/cur_freq").read()) // 1_000_000
    except OSError:
        return 0


def battery_ma():
    try:
        return int(open("/sys/class/power_supply/battery/current_now").read()) // 1000
    except OSError:
        return None


def run(name, cmd, warm, seconds):
    proc = subprocess.Popen(cmd, env=ENV, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(warm)
    pgid = proc.pid
    t0, _ = sample(pgid)
    freqs = []
    start = time.time()
    while time.time() - start < seconds:
        freqs.append(gpu_mhz())
        time.sleep(0.25)
    t1, rss = sample(pgid)
    wall = time.time() - start
    try:
        os.killpg(pgid, signal.SIGKILL)
    except OSError:
        pass
    proc.wait()
    time.sleep(2)
    return {
        "scenario": name,
        "cpu_pct_one_core": round((t1 - t0) * 100 / (HZ * wall)),
        "rss_mb": rss,
        "gpu_mhz_avg": round(statistics.mean(freqs)) if freqs else 0,
        "gpu_at_max_pct": round(100 * sum(1 for f in freqs if f >= gpu_max_mhz()) / len(freqs)) if freqs else 0,
        "battery_ma": battery_ma(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=os.path.expanduser(
        "~/Downloads/media/h264-1080p-test.mkv"),
        help="1080p24 test clip, looped for the whole run")
    ap.add_argument("--seconds", type=int, default=12)
    ap.add_argument("--warm", type=int, default=7)
    ap.add_argument("--only", nargs="*", help="subset of scenario names")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()

    rows = []
    for name, cmd, _needs_va in scenarios(args.file):
        if args.only and name not in args.only:
            continue
        row = run(name, cmd, args.warm, args.seconds)
        rows.append(row)
        if not args.markdown:
            print(json.dumps(row), flush=True)

    if args.markdown:
        print("| configuration | CPU (1 core) | RAM | GPU (devfreq avg) "
              "| battery |")
        print("|---|---|---|---|---|")
        for r in rows:
            print(f"| {r['scenario']} | {r['cpu_pct_one_core']} % "
                  f"| {r['rss_mb']} MB | {r['gpu_mhz_avg']} MHz "
                  f"| {r['battery_ma']} mA |")


if __name__ == "__main__":
    main()
