"""Commands supported by the terminal's interactive SSH API."""

from __future__ import annotations

import re


_SAFE_KEY = re.compile(r"^[A-Za-z0-9_+\-]+$")
_KEY_ALIASES = {
    "*": "asterisk",
    "#": "numbersign",
    "Break": "Pause",
    "KP_Enter": "KP_Enter",
    "Prior": "Page_Up",
    "Next": "Page_Down",
    "Escape": "Escape",
    "BackSpace": "BackSpace",
    "space": "space",
}
_IGNORED_KEYS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Super_L", "Super_R", "Caps_Lock",
}
_REMOTE_BUTTONS = {
    "call", "volume+", "volume-", "zoom+", "zoom-", "home", "back",
    "save", "power", "pc", "far", "layout", "mute",
}


def key_command(keysym: str, state: int = 0, hold_ms: int | None = None) -> bytes | None:
    """Build a documented ``button key <xdotool-key>`` SSH API request."""
    if keysym in _IGNORED_KEYS:
        return None
    key = _KEY_ALIASES.get(keysym, keysym)
    if not _SAFE_KEY.fullmatch(key):
        return None

    modifiers: list[str] = []
    if state & 0x4:
        modifiers.append("ctrl")
    if state & 0x8:
        modifiers.append("alt")
    if state & 0x1 and len(key) > 1:
        modifiers.append("shift")
    if modifiers:
        key = "+".join((*modifiers, key))
    timing = "" if hold_ms is None else f"-t {max(50, min(hold_ms, 30000))} "
    return f"button {timing}key {key}\n".encode("ascii")


def remote_button_command(name: str) -> bytes:
    if name not in _REMOTE_BUTTONS:
        raise ValueError(f"unsupported remote button: {name}")
    return f"button {name}\n".encode("ascii")


def hangup_command() -> bytes:
    return b"hangup all\n"
