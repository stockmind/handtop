#!/usr/bin/env python3
"""goblin-dash — a tiny TUI status dashboard for the RG35XX H ("goblin").

Designed for a 640x480 panel and a 1 GB / 4-core box: no dependencies beyond
the Python 3 standard library, refreshes by re-reading cheap /sys + /proc
counters, and optionally shows what Jellyfin is playing on the LAN.

Run with no args for a live auto-refreshing view (q or Ctrl-C to quit).
Pass --once to print a single frame and exit (handy for scripts/keybinds).

Environment:
  DASH_JELLYFIN   http://host:port of Jellyfin (default empty = off)
  DASH_API_KEY    Jellyfin API key (optional; enables now-playing)
  DASH_INTERVAL   refresh seconds (default 2)

Quick links (press a number while running):
  1  Dashboard     this view (no-op if already here)
  2  Play media    goblin-play
  3  Music         goblin-music
  4  htop          process monitor
  5  Files         thunar
  6  Screen off    wlopm --off
  q  Quit
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import termios
import time
import tty
import urllib.error
import urllib.request

JELLYFIN = os.environ.get("DASH_JELLYFIN", "").rstrip("/")
API_KEY = os.environ.get("DASH_API_KEY", "")
INTERVAL = float(os.environ.get("DASH_INTERVAL", "2"))

QUICK_LINKS = [
    ("1", "Play media", "goblin-play"),
    ("2", "Music", "goblin-music"),
    ("3", "htop", "htop"),
    ("4", "Files", "thunar"),
    ("5", "Screen off", "wlopm --off '*'"),
]


def read(path, default="?"):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def bar(frac, width=18):
    if frac is None:
        return "[" + "?" * width + "]"
    frac = max(0.0, min(1.0, frac))
    filled = int(round(frac * width))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def meminfo():
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, v = line.partition(":")
                info[k] = int(v.strip().split()[0])  # kB
    except OSError:
        return None
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    if not total:
        return None
    used = total - avail
    return used / 1024.0, total / 1024.0, used / total


def cpu_load():
    try:
        with open("/proc/loadavg") as f:
            parts = f.read().split()
        return [float(x) for x in parts[:3]]
    except (OSError, ValueError):
        return None


def cpu_temp():
    # thermal zones expose millidegrees; pick the SoC zone (first readable).
    import glob
    for z in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
        raw = read(z)
        if raw != "?":
            try:
                return int(raw) / 1000.0
            except ValueError:
                pass
    return None


def battery():
    base = "/sys/class/power_supply"
    if not os.path.isdir(base):
        return None
    for psu in os.listdir(base):
        cap = read(f"{base}/{psu}/capacity")
        if cap == "?":
            continue
        status = read(f"{base}/{psu}/status", "?")
        try:
            return int(cap), status
        except ValueError:
            pass
    return None


def storage(path="/"):
    try:
        u = shutil.disk_usage(path)
    except OSError:
        return None
    return u.used / u.total, u.free / (1024 ** 3)


def net_ip():
    ip = "?"
    try:
        # No socket-connect needed: read the first global IPv4 from `ip -o`.
        out = subprocess.run(
            ["ip", "-o", "-4", "addr", "show", "scope", "global"],
            capture_output=True, text=True, timeout=3,
        ).stdout
        for line in out.splitlines():
            toks = line.split()
            if "inet" in toks:                      # ... inet <addr>/<mask> ...
                ip = toks[toks.index("inet") + 1].split("/")[0]
                break
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return ip


def jellyfin_now():
    """Return a short now-playing string from Jellyfin, or '' when unavailable."""
    if not JELLYFIN:
        return ""
    # Jellyfin 12+ requires Authorization: MediaBrowser Token="…" (not X-Emby-Token).
    url = f"{JELLYFIN}/Sessions"
    auth = f'MediaBrowser Token="{API_KEY}"' if API_KEY else None
    req = urllib.request.Request(url, headers={"Authorization": auth} if auth else {})
    try:
        with urllib.request.urlopen(req, timeout=2.5) as r:
            data = json.load(r)
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return "jellyfin: unreachable"
    for s in data:
        now = s.get("NowPlayingItem")
        if not now:
            continue
        title = now.get("SeriesName") or now.get("Name") or "?"
        if now.get("IndexNumber") is not None:
            title += f" s{now.get('ParentIndexNumber', '?')}e{now['IndexNumber']}"
        play = s.get("NowPlayingQueue") and s["PlayState"] or {}
        pos = play.get("PositionTicks", 0) / 1e7
        state = "▶" if not play.get("Paused") else "⏸"
        client = s.get("Client", "?")
        mm, ss = divmod(int(pos), 60)
        return f"{state} {title}  [{mm}:{ss:02d}]  ({client})"
    return "jellyfin: idle"


def uptime_str():
    raw = read("/proc/uptime")
    if raw == "?":
        return "?"
    secs = float(raw.split()[0])
    d, rem = divmod(int(secs), 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    return (f"{d}d " if d else "") + f"{h}h {m:02d}m"


def render(width):
    lines = []
    title = " goblin ".center(width, "=")
    lines.append(title)

    load = cpu_load()
    if load:
        ncpu = os.cpu_count() or 1
        lines.append(f"Load    {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}  ({ncpu} cores)")
    temp = cpu_temp()
    lines.append(f"Temp    {temp:.0f} C" if temp is not None else "Temp    ?")

    mem = meminfo()
    if mem:
        used, total, frac = mem
        lines.append(f"Memory  {bar(frac)} {used:.0f}/{total:.0f} MB")

    st = storage()
    if st:
        frac, free_gb = st
        lines.append(f"D      {bar(frac)} {free_gb:.0f} GB free")

    bat = battery()
    if bat:
        cap, status = bat
        lines.append(f"Battery {bar(cap / 100)} {cap}%  {status}")

    lines.append(f"IP      {net_ip()}")
    lines.append(f"Up      {uptime_str()}")

    jp = jellyfin_now()
    if jp:
        lines.append("-" * width)
        lines.append(jp[:width])
    lines.append("=" * width)

    # quick-links footer (only when interactive)
    links_line = "  ".join(f"{key}:{name}" for key, name, _ in QUICK_LINKS)
    lines.append(links_line)

    return "\n".join(lines)


def main():
    once = "--once" in sys.argv
    try:
        width = min(shutil.get_terminal_size((40, 12)).columns, 44)
    except Exception:
        width = 40
    if once:
        print(render(width))
        return

    # interactive loop: refresh every INTERVAL seconds; check for a keypress.
    # Pressing a number launches the matching tool (in a new terminal or inline).
    old_settings = None
    if sys.stdin.isatty():
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    def read_key(timeout):
        """Return one character from stdin within timeout, else ''."""
        import select
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        return sys.stdin.read(1) if rlist else ""

    try:
        while True:
            frame = render(width)
            sys.stdout.write("\033[H\033[J")  # home + clear (no flicker)
            sys.stdout.write(frame + "\n")
            sys.stdout.flush()

            key = read_key(INTERVAL)
            if key == "q":
                break
            elif key and not key.isspace():
                # match quick-link by digit
                action_cmd = next((cmd for k, name, cmd in QUICK_LINKS if k == key), None)
                if action_cmd:
                    subprocess.run(["sh", "-c", action_cmd])
                    # after returning from the launched tool, redraw immediately
    finally:
        if old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


if __name__ == "__main__":
    main()
