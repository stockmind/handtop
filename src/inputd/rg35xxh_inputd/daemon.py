"""rg35xxh-inputd: turns the RG35XX H controls into mouse/keyboard (desktop mode) or an
Xbox-style controller (gamepad mode). Runs inside the labwc session as the user.

Devices (grabbed exclusively while running):
  "H700 Gamepad"              buttons + sticks (+ rumble motor)
  device with KEY_VOLUMEUP    volume keys (gpio-keys)
  device with KEY_POWER       power button (AXP717)
Virtual devices (uinput): mouse, keyboard, and in gamepad mode an Xbox 360 pad.
"""
import logging
import os
import shutil
import signal
import struct
import subprocess
import sys
import time

import evdev
from evdev import ecodes as E
from evdev import ff
from gi.repository import GLib

from . import config
from .core import Core

log = logging.getLogger("rg35xxh-inputd")

GAMEPAD_NAME = "H700 Gamepad"
BUILTIN = {GAMEPAD_NAME: "gamepad", "gpio-keys-volume": "volume", "axp20x-pek": "power"}
# Physical codes (rocknix-singleadc-joypad, see docs/hardware.md) -> button names.
HW_BUTTONS = {
    0x131: "a", 0x130: "b", 0x134: "x", 0x133: "y",   # all four verified on device (debug log)
    0x136: "l1", 0x137: "r1", 0x138: "l2", 0x139: "r2",
    0x13d: "l3", 0x13e: "r3", 0x13a: "select", 0x13b: "start", 0x13c: "f",
    0x220: "up", 0x221: "down", 0x222: "left", 0x223: "right",
    E.KEY_VOLUMEUP: "vol_up", E.KEY_VOLUMEDOWN: "vol_down", E.KEY_POWER: "power",
}
HW_AXES = {E.ABS_X: "lx", E.ABS_Y: "ly", E.ABS_RX: "rx", E.ABS_RY: "ry"}
TERMINALS = ("foot", "footclient", "org.codeberg.dnkl.foot", "xterm", "uxterm", "kitty", "alacritty")
STATUS_LED = "/sys/class/leds/red:status"


def runtime_flag(name):
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), name)


def spawn(*argv):
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as e:
        log.warning("cannot run %s: %s", argv[0], e)


class Daemon:
    def __init__(self):
        settings, bindings, self.hw, self.config_path = config.load()
        self.core = Core(settings, bindings)
        self.devices = []          # grabbed physical devices
        self.gamepad = None
        self.absinfo = {}
        self.pad = None            # virtual Xbox pad (gamepad mode only)
        self.pad_ff = {}           # virtual effect id -> physical effect id
        self.haptic_id = None
        self.axis_offset = {}      # software centre correction per axis (set by re-centre)
        self.watches = {}          # fd -> GLib watch id
        self.osk = None
        self.ticks = 0
        self._open_devices()
        self._create_virtual_devices()
        self._init_osk()

    # ------------------------------------------------------------ devices
    def _open_devices(self, wait=15.0):
        deadline = time.monotonic() + wait
        found = {}
        while time.monotonic() < deadline:
            for path in evdev.list_devices():
                try:
                    d = evdev.InputDevice(path)
                except OSError:
                    continue
                # Match the built-in devices by name: USB/BT keyboards also report
                # KEY_VOLUMEUP / KEY_POWER and must not be grabbed.
                role = BUILTIN.get(d.name)
                if role and role not in found:
                    found[role] = d
                else:
                    d.close()
            if len(found) == len(BUILTIN):
                break
            time.sleep(0.5)
        for role, d in found.items():
            try:
                d.grab()
            except OSError as e:
                log.error("cannot grab %s (%s): %s", role, d.path, e)
                continue
            log.info("%s: %s (%s)", role, d.name, d.path)
            self.devices.append(d)
        self.gamepad = found.get("gamepad")
        if not self.gamepad:
            log.error("gamepad '%s' not found", GAMEPAD_NAME)
        else:
            self._setup_gamepad()
        for d in self.devices:
            self._watch(d)

    def _watch(self, d):
        self.watches[d.fd] = GLib.io_add_watch(d.fd, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
                                               self._on_device, d)

    def _setup_gamepad(self):
        self.absinfo = {}
        for code, info in self.gamepad.capabilities().get(E.EV_ABS, []):
            self.absinfo[code] = info
        self.haptic_id = None
        if E.EV_FF in self.gamepad.capabilities():
            try:
                rumble = ff.Rumble(strong_magnitude=0xFFFF, weak_magnitude=0xFFFF)
                eff = ff.Effect(E.FF_RUMBLE, -1, 0, ff.Trigger(0, 0), ff.Replay(450, 0),
                                ff.EffectType(ff_rumble_effect=rumble))
                self.haptic_id = self.gamepad.upload_effect(eff)
            except OSError as e:
                log.warning("rumble not available: %s", e)

    # ---------------------------------------------------- stick re-centre
    # The stick driver (rocknix-singleadc-joypad) measures each axis' centre ONCE, from a single
    # ADC reading, when the device is first opened; a bad reading leaves a stick drifting until
    # the device is reopened. We are the only user of the device, so closing and reopening it
    # makes the driver measure the centre again. Any axis still off-centre afterwards gets a
    # software correction. Triggered by SIGUSR1 (the "Re-center sticks" app).
    RECENTER_THRESHOLD = 0.08      # fraction of full travel still counted as "off-centre"

    def _recenter(self):
        g = self.gamepad
        if g is None:
            spawn("notify-send", "-t", "4000", "Re-center sticks", "Gamepad not found")
            return True
        log.info("re-centre: reopening %s", g.path)
        path = g.path
        wid = self.watches.pop(g.fd, None)
        if wid:
            GLib.source_remove(wid)
        try:
            g.ungrab()
        except OSError:
            pass
        g.close()
        self.devices.remove(g)
        self.pad_ff = {}           # effects lived on the old file handle
        time.sleep(0.2)
        try:
            g = evdev.InputDevice(path)
            g.grab()
        except OSError as e:
            log.error("re-centre: cannot reopen %s: %s; restarting", path, e)
            GLib.idle_add(self._quit)
            return True
        self.gamepad = g
        self.devices.append(g)
        self._setup_gamepad()
        self._watch(g)

        # Verify: sample the axes for ~0.5 s and correct what is still off-centre.
        samples = {code: [] for code in HW_AXES}
        for _ in range(10):
            time.sleep(0.05)
            for code in HW_AXES:
                samples[code].append(g.absinfo(code).value)
        self.axis_offset = {}
        report = []
        for code, vals in samples.items():
            info = self.absinfo.get(code)
            if not info or info.max == info.min:
                continue
            half = (info.max - info.min) / 2.0
            avg = sum(vals) / len(vals)
            steady = (max(vals) - min(vals)) <= 2 * max(info.fuzz, 1) + 8
            if steady and abs(avg) > self.RECENTER_THRESHOLD * half:
                self.axis_offset[code] = int(round(avg))
            report.append("%s %+d%%" % (HW_AXES[code], round(100 * avg / half)))
        now = time.monotonic()
        for name in HW_AXES.values():
            self._run(self.core.axis(name, 0.0, now))
        log.info("re-centre: driver centre re-measured; rest %s; software offsets %s",
                 ", ".join(report), self.axis_offset or "none")
        self._haptic()
        msg = "Sticks re-centered." + (" Correction applied to " + ", ".join(HW_AXES[c] for c in self.axis_offset)
                                       if self.axis_offset else "")
        spawn("notify-send", "-t", "4000", "Re-center sticks", msg)
        return True

    def _create_virtual_devices(self):
        self.mouse = evdev.UInput({
            E.EV_KEY: [E.BTN_LEFT, E.BTN_RIGHT, E.BTN_MIDDLE],
            E.EV_REL: [E.REL_X, E.REL_Y, E.REL_WHEEL, E.REL_HWHEEL, E.REL_WHEEL_HI_RES, E.REL_HWHEEL_HI_RES],
        }, name="rg35xxh virtual mouse")
        # No power/sleep keys: logind would otherwise watch this device for them.
        keys = [k for k in range(1, 249) if k not in (E.KEY_POWER, E.KEY_SLEEP, E.KEY_SUSPEND, E.KEY_WAKEUP)]
        self.keyboard = evdev.UInput({E.EV_KEY: keys}, name="rg35xxh virtual keyboard")

    def _create_pad(self):
        caps = {
            E.EV_KEY: [E.BTN_A, E.BTN_B, E.BTN_X, E.BTN_Y, E.BTN_TL, E.BTN_TR, E.BTN_SELECT,
                       E.BTN_START, E.BTN_MODE, E.BTN_THUMBL, E.BTN_THUMBR],
            E.EV_ABS: [(c, evdev.AbsInfo(0, -32768, 32767, 16, 128, 0)) for c in (E.ABS_X, E.ABS_Y, E.ABS_RX, E.ABS_RY)]
            + [(c, evdev.AbsInfo(0, 0, 255, 0, 0, 0)) for c in (E.ABS_Z, E.ABS_RZ)]
            + [(c, evdev.AbsInfo(0, -1, 1, 0, 0, 0)) for c in (E.ABS_HAT0X, E.ABS_HAT0Y)],
            E.EV_FF: [E.FF_RUMBLE],
        }
        # Identify as an Xbox 360 controller so SDL/Moonlight use the standard mapping.
        self.pad = evdev.UInput(caps, name="Microsoft X-Box 360 pad", vendor=0x045E, product=0x028E,
                                version=0x110, bustype=E.BUS_USB, max_effects=16)
        self.pad_ff = {}
        self.pad_watch = GLib.io_add_watch(self.pad.fd, GLib.IO_IN, self._on_pad_fd)
        log.info("gamepad mode: virtual Xbox pad created")

    def _destroy_pad(self):
        if self.pad:
            GLib.source_remove(self.pad_watch)
            for phys in self.pad_ff.values():
                try:
                    self.gamepad.erase_effect(phys)
                except OSError:
                    pass
            self.pad.close()
            self.pad = None
            log.info("desktop mode: virtual pad removed")

    # ---------------------------------------------------------------- OSK
    def _init_osk(self):
        try:
            from . import osk
            self.osk = osk.OnScreenKeyboard(self._type_combo)
        except Exception as e:  # no display / missing GTK layer shell
            log.warning("on-screen keyboard unavailable: %s", e)

    def _type_combo(self, mods, key):
        codes = [E.ecodes[m] for m in mods]
        k = E.ecodes[key]
        for c in codes:
            self.keyboard.write(E.EV_KEY, c, 1)
        self.keyboard.write(E.EV_KEY, k, 1)
        self.keyboard.syn()
        self.keyboard.write(E.EV_KEY, k, 0)
        for c in reversed(codes):
            self.keyboard.write(E.EV_KEY, c, 0)
        self.keyboard.syn()

    # ------------------------------------------------------------- events
    def _on_device(self, fd, cond, dev):
        if cond & (GLib.IO_HUP | GLib.IO_ERR):
            # Built-in devices can be re-created (e.g. after resume): exit and let the
            # session's restart loop start a fresh daemon that opens them again.
            log.error("device lost: %s (%s), restarting", dev.path, dev.name)
            GLib.idle_add(self._quit)
            return False
        now = time.monotonic()
        try:
            for ev in dev.read():
                if ev.type == E.EV_KEY and ev.value in (0, 1):
                    log.debug("key 0x%x %s -> %s", ev.code, "down" if ev.value else "up",
                              HW_BUTTONS.get(ev.code))
                if ev.type == E.EV_KEY and ev.code in HW_BUTTONS and ev.value in (0, 1):
                    self._run(self.core.button(HW_BUTTONS[ev.code], ev.value == 1, now))
                elif ev.type == E.EV_ABS and ev.code in HW_AXES:
                    self._run(self.core.axis(HW_AXES[ev.code], self._norm(ev.code, ev.value), now))
        except BlockingIOError:
            pass
        except OSError as e:
            log.error("read error on %s: %s", dev.path, e)
        return True

    def _norm(self, code, value):
        info = self.absinfo.get(code)
        if not info or info.max == info.min:
            return 0.0
        value -= self.axis_offset.get(code, 0)
        mid = (info.max + info.min) / 2.0
        v = (value - mid) / ((info.max - info.min) / 2.0)
        if self.hw.get("invert_" + HW_AXES[code]):
            v = -v
        return v

    def _tick(self):
        self.ticks += 1
        now = time.monotonic()
        if self.ticks % 10 == 0:
            self.core.set_screen_off(os.path.exists(runtime_flag("rg35xxh-screen-off")))
            if self.osk:
                self.core.set_osk_visible(self.osk.visible)
        self._run(self.core.tick(now))
        return True

    # ------------------------------------------------------------ actions
    def _run(self, actions):
        mouse_dirty = False
        for a in actions:
            kind = a[0]
            if kind == "rel":
                self.mouse.write(E.EV_REL, E.REL_X, a[1])
                self.mouse.write(E.EV_REL, E.REL_Y, a[2])
                mouse_dirty = True
            elif kind == "wheel":
                if a[1]:
                    self.mouse.write(E.EV_REL, E.REL_WHEEL_HI_RES, a[1])
                    self._wheel_notch(E.REL_WHEEL, a[1], 0)
                if a[2]:
                    self.mouse.write(E.EV_REL, E.REL_HWHEEL_HI_RES, a[2])
                    self._wheel_notch(E.REL_HWHEEL, a[2], 1)
                mouse_dirty = True
            elif kind == "mouse":
                btn = {"left": E.BTN_LEFT, "right": E.BTN_RIGHT, "middle": E.BTN_MIDDLE}[a[1]]
                self.mouse.write(E.EV_KEY, btn, 1 if a[2] else 0)
                mouse_dirty = True
            elif kind == "key":
                self.keyboard.write(E.EV_KEY, E.ecodes[a[1]], 1 if a[2] else 0)
                self.keyboard.syn()
            elif kind == "clipboard":
                self._clipboard(a[1])
            elif kind == "osk" and not self.osk:
                log.warning("on-screen keyboard requested but unavailable")
            elif kind == "osk" and self.osk:
                if a[1] == "toggle":
                    self.osk.toggle()
                    self.core.set_osk_visible(self.osk.visible)
                    log.info("on-screen keyboard %s", "shown" if self.osk.visible else "hidden")
                elif a[1] == "move":
                    self.osk.move(a[2], a[3])
                elif a[1] == "press":
                    self.osk.press_selected()
                elif a[1] == "release":
                    self.osk.release_selected()
            elif kind == "mode":
                if a[1] == "gamepad":
                    if self.osk and self.osk.visible:
                        self.osk.toggle()
                    self._create_pad()
                    open(runtime_flag("rg35xxh-gamepad-mode"), "w").close()   # read by rg35xxh-autosleep
                    spawn("notify-send", "-t", "2500", "Gamepad mode", "Hold Start for 1 s to return to desktop mode")
                else:
                    self._destroy_pad()
                    try:
                        os.unlink(runtime_flag("rg35xxh-gamepad-mode"))
                    except FileNotFoundError:
                        pass
                    if a[1] == "keys":
                        spawn("notify-send", "-t", "2500", "Keypad mode", "D-pad moves, A selects, Select returns to desktop")
                    else:
                        spawn("notify-send", "-t", "1500", "Desktop mode")
            elif kind == "pad_key" and self.pad:
                self.pad.write(E.EV_KEY, E.ecodes[a[1]], a[2])
                self.pad.syn()
            elif kind == "pad_abs" and self.pad:
                self.pad.write(E.EV_ABS, E.ecodes[a[1]], a[2])
                self.pad.syn()
            elif kind == "cmd":
                self._command(a[1])
            elif kind == "screen_wake":
                spawn("rg35xxh-screen-on")
            elif kind == "shutdown":
                self._shutdown()
        if mouse_dirty:
            self.mouse.syn()

    def _wheel_notch(self, code, hires, idx):
        # Legacy wheel events for apps without hi-res support: one per 120 units.
        acc = getattr(self, "_notch_acc", [0, 0])
        acc[idx] += hires
        notches = int(acc[idx] / 120)
        if notches:
            acc[idx] -= notches * 120
            self.mouse.write(E.EV_REL, code, notches)
        self._notch_acc = acc

    def _clipboard(self, what):
        letter = "KEY_C" if what == "copy" else "KEY_V"
        mods = ["KEY_LEFTCTRL"]
        if self._focused_is_terminal():
            mods.append("KEY_LEFTSHIFT")
        self._type_combo(mods, letter)

    def _focused_is_terminal(self):
        # One query: repeated app_id matches are OR-ed by wlrctl; state:active = focused window.
        if not shutil.which("wlrctl"):
            return False
        argv = ["wlrctl", "toplevel", "find"] + ["app_id:" + a for a in TERMINALS] + ["state:active"]
        try:
            return subprocess.run(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  timeout=0.5).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _command(self, name):
        if name == "power_menu":
            spawn("rg35xxh-power-menu")
        elif name in ("volume_up", "volume_down"):
            step = "5%+" if name == "volume_up" else "5%-"
            try:
                subprocess.run(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", step],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                out = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"], capture_output=True,
                                     text=True, timeout=1).stdout       # "Volume: 0.55 [MUTED]"
                vol = round(float(out.split()[1]) * 100)
                self._osd(0 if "MUTED" in out else vol, "volume")
            except (OSError, subprocess.TimeoutExpired, ValueError, IndexError) as e:
                log.warning("volume: %s", e)
        elif name in ("brightness_up", "brightness_down"):
            self._brightness(+1 if name == "brightness_up" else -1)

    BACKLIGHT = "/sys/class/backlight/backlight"
    BRIGHTNESS_MIN = 0.05      # never fully dark
    BRIGHTNESS_STEP = 0.10

    def _brightness(self, direction):
        try:
            with open(self.BACKLIGHT + "/max_brightness") as f:
                mx = int(f.read())
            with open(self.BACKLIGHT + "/brightness") as f:
                cur = int(f.read())
            new = cur + direction * round(mx * self.BRIGHTNESS_STEP)
            new = max(round(mx * self.BRIGHTNESS_MIN), min(mx, new))
            with open(self.BACKLIGHT + "/brightness", "w") as f:
                f.write(str(new))
            self._osd(round(new * 100 / mx), "brightness")
        except (OSError, ValueError) as e:
            log.warning("brightness: %s", e)

    def _osd(self, percent, style):
        """Show a volume/brightness bar: one wob per kind (wob 0.14 has no per-value styles),
        fed through $XDG_RUNTIME_DIR/wob-<kind>.sock, started by the session autostart."""
        path = runtime_flag(f"wob-{style}.sock")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_NONBLOCK)
        except OSError:
            return  # no OSD running
        try:
            os.write(fd, f"{max(0, min(100, percent))}\n".encode())
        except OSError:
            pass
        finally:
            os.close(fd)

    def _shutdown(self):
        log.info("power held: shutting down")
        self._haptic()
        try:
            with open(os.path.join(STATUS_LED, "trigger"), "w") as f:
                f.write("timer")
        except OSError as e:
            log.warning("status LED: %s", e)
        spawn("notify-send", "-u", "critical", "-t", "10000", "Shutting down…")
        GLib.timeout_add(600, lambda: spawn("systemctl", "poweroff") or False)

    def _haptic(self):
        if self.gamepad is not None and self.haptic_id is not None:
            try:
                self.gamepad.write(E.EV_FF, self.haptic_id, 1)
            except OSError as e:
                log.warning("rumble failed: %s", e)

    # ------------------------------------------- rumble from the virtual pad
    _EV = struct.Struct("llHHi")

    def _on_pad_fd(self, fd, cond):
        if not self.pad:
            return False
        try:
            data = os.read(fd, self._EV.size * 16)
        except BlockingIOError:
            return True
        except OSError:
            return True
        for i in range(0, len(data) - self._EV.size + 1, self._EV.size):
            _, _, etype, code, value = self._EV.unpack_from(data, i)
            try:
                if etype == E.EV_UINPUT and code == E.UI_FF_UPLOAD:
                    up = self.pad.begin_upload(value)
                    vid = up.effect.id
                    existing = self.pad_ff.get(vid)
                    up.effect.id = existing if existing is not None else -1
                    self.pad_ff[vid] = self.gamepad.upload_effect(up.effect)
                    up.effect.id = vid
                    up.retval = 0
                    self.pad.end_upload(up)
                elif etype == E.EV_UINPUT and code == E.UI_FF_ERASE:
                    er = self.pad.begin_erase(value)
                    phys = self.pad_ff.pop(er.effect_id, None)
                    if phys is not None:
                        self.gamepad.erase_effect(phys)
                    er.retval = 0
                    self.pad.end_erase(er)
                elif etype == E.EV_FF and code in self.pad_ff:
                    self.gamepad.write(E.EV_FF, self.pad_ff[code], value)
            except Exception as e:  # rumble is best effort
                log.debug("rumble forward: %s", e)
        return True

    # ---------------------------------------------------------------- run
    def _quit(self):
        if self.osk:
            from gi.repository import Gtk
            Gtk.main_quit()
        else:
            self._loop.quit()
        return False

    def run(self):
        GLib.timeout_add(10, self._tick)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self._recenter)
        self._loop = None
        try:
            if self.osk:
                from gi.repository import Gtk
                Gtk.main()
            else:
                self._loop = GLib.MainLoop()
                self._loop.run()
        finally:
            for d in self.devices:
                try:
                    d.ungrab()
                except OSError:
                    pass


def main():
    # Touch $XDG_RUNTIME_DIR/rg35xxh-inputd.debug and restart the daemon to log every key event.
    debug = os.path.exists(runtime_flag("rg35xxh-inputd.debug"))
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(message)s")
    Daemon().run()


if __name__ == "__main__":
    main()
