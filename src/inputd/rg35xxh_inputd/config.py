"""Config file loading. First existing file wins:
   /boot/firmware/rg35xxh-input.conf   (FAT boot partition, editable from Windows)
   /etc/rg35xxh/input.conf             (system default)
"""
import configparser
import logging
import re

from .core import DEFAULT_BINDINGS, DEFAULT_SETTINGS

PATHS = ("/boot/firmware/rg35xxh-input.conf", "/etc/rg35xxh/input.conf")
BUTTON_NAMES = tuple(DEFAULT_BINDINGS)
_ACTION_RE = re.compile(r"^(none|click_(left|right|middle)|key:KEY_[A-Z0-9_]+|copy|paste|osk_toggle|mode_gamepad|mode_keys|power_menu)$")

log = logging.getLogger("rg35xxh-inputd")


def load(paths=PATHS):
    settings, bindings, hardware = {}, {}, {"invert_ly": False, "invert_ry": False, "invert_lx": False, "invert_rx": False}
    cp = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    used = None
    for p in paths:
        try:
            with open(p, encoding="utf-8-sig") as f:   # tolerate a BOM from Windows editors
                cp.read_file(f)
            used = p
            break
        except FileNotFoundError:
            continue
        except (OSError, configparser.Error) as e:
            log.warning("cannot read %s: %s", p, e)
    if used:
        log.info("config: %s", used)
    if cp.has_section("settings"):
        for k, v in cp.items("settings"):
            if k in DEFAULT_SETTINGS:
                try:
                    settings[k] = float(v)
                except ValueError:
                    log.warning("settings.%s: not a number: %r", k, v)
            else:
                log.warning("settings.%s: unknown setting", k)
    if cp.has_section("desktop"):
        for k, v in cp.items("desktop"):
            v = v.strip()
            if k not in BUTTON_NAMES:
                log.warning("desktop.%s: unknown button (valid: %s)", k, ", ".join(BUTTON_NAMES))
            elif not _ACTION_RE.match(v):
                log.warning("desktop.%s: unknown action %r", k, v)
            else:
                bindings[k] = v
    if cp.has_section("hardware"):
        for k in hardware:
            if cp.has_option("hardware", k):
                hardware[k] = cp.getboolean("hardware", k, fallback=False)
    return settings, bindings, hardware, used
