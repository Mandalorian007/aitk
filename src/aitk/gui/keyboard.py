"""Keyboard control using Quartz CoreGraphics."""

import time
from .errors import require_macos

require_macos()

from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGHIDEventTap,
    kCGEventFlagMaskShift,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
)

# Virtual keycode mapping for macOS
# Reference: HIToolbox/Events.h, Carbon Events
KEYCODES: dict[str, int] = {
    # Letters
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
    "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
    "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28, "0": 29,
    "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "l": 37,
    "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44,
    "n": 45, "m": 46, ".": 47,
    # Special keys
    "return": 36, "enter": 36,
    "tab": 48,
    "space": 49,
    "delete": 51, "backspace": 51,
    "escape": 53, "esc": 53,
    "command": 55, "cmd": 55,
    "shift": 56,
    "capslock": 57,
    "option": 58, "alt": 58,
    "control": 59, "ctrl": 59,
    "rightshift": 60,
    "rightoption": 61, "rightalt": 61,
    "rightcontrol": 62, "rightctrl": 62,
    "fn": 63,
    # Function keys
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "f13": 105, "f14": 107, "f15": 113, "f16": 106, "f17": 64, "f18": 79,
    "f19": 80, "f20": 90,
    # Arrow keys
    "up": 126, "down": 125, "left": 123, "right": 124,
    # Navigation
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    "forwarddelete": 117,
    # Numpad
    "numpad0": 82, "numpad1": 83, "numpad2": 84, "numpad3": 85,
    "numpad4": 86, "numpad5": 87, "numpad6": 88, "numpad7": 89,
    "numpad8": 91, "numpad9": 92,
    "numpadclear": 71, "numpadenter": 76, "numpaddivide": 75,
    "numpadmultiply": 67, "numpadminus": 78, "numpadplus": 69,
    "numpaddecimal": 65, "numpadequals": 81,
    # Symbols (with shift)
    "`": 50, "~": 50,
}

# Characters that require shift
SHIFT_CHARS = set('~!@#$%^&*()_+{}|:"<>?ABCDEFGHIJKLMNOPQRSTUVWXYZ')

# Modifier key names to flags
MODIFIER_FLAGS: dict[str, int] = {
    "shift": kCGEventFlagMaskShift,
    "control": kCGEventFlagMaskControl,
    "ctrl": kCGEventFlagMaskControl,
    "option": kCGEventFlagMaskAlternate,
    "alt": kCGEventFlagMaskAlternate,
    "command": kCGEventFlagMaskCommand,
    "cmd": kCGEventFlagMaskCommand,
}

# Shift-modified character mappings
SHIFT_MAP: dict[str, str] = {
    "~": "`", "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0", "_": "-",
    "+": "=", "{": "[", "}": "]", "|": "\\", ":": ";", '"': "'",
    "<": ",", ">": ".", "?": "/",
}


def _get_keycode(char: str) -> tuple[int, bool]:
    """Get keycode and whether shift is needed for a character.

    Returns:
        (keycode, needs_shift) tuple.

    Raises:
        ValueError: If character has no known keycode.
    """
    lower = char.lower()

    # Check if it's a shifted version
    if char in SHIFT_MAP:
        base_char = SHIFT_MAP[char]
        if base_char in KEYCODES:
            return KEYCODES[base_char], True

    # Check direct mapping
    if lower in KEYCODES:
        needs_shift = char in SHIFT_CHARS
        return KEYCODES[lower], needs_shift

    raise ValueError(f"No keycode mapping for: {char!r}")


def _press_key(keycode: int, flags: int = 0) -> None:
    """Press and release a single key with optional modifier flags."""
    down = CGEventCreateKeyboardEvent(None, keycode, True)
    up = CGEventCreateKeyboardEvent(None, keycode, False)

    if flags:
        CGEventSetFlags(down, flags)
        CGEventSetFlags(up, flags)

    CGEventPost(kCGHIDEventTap, down)
    CGEventPost(kCGHIDEventTap, up)


def type_text(text: str, delay: float = 0.02) -> None:
    """Type a string of text.

    Args:
        text: Text to type.
        delay: Delay between keystrokes in seconds.
    """
    for char in text:
        try:
            keycode, needs_shift = _get_keycode(char)
            flags = kCGEventFlagMaskShift if needs_shift else 0
            _press_key(keycode, flags)
            time.sleep(delay)
        except ValueError:
            # Skip characters we can't type
            continue


def hotkey(combo: str) -> None:
    """Execute a hotkey combination.

    Args:
        combo: Key combination like "cmd+c", "ctrl+shift+a", "cmd+option+esc".
    """
    parts = combo.lower().replace("-", "+").split("+")
    parts = [p.strip() for p in parts if p.strip()]

    if not parts:
        raise ValueError("Empty hotkey combination")

    # Separate modifiers from the final key
    modifiers = []
    key = None

    for part in parts:
        if part in MODIFIER_FLAGS:
            modifiers.append(part)
        else:
            if key is not None:
                raise ValueError(f"Multiple non-modifier keys in combo: {combo}")
            key = part

    if key is None:
        raise ValueError(f"No key specified in combo: {combo}")

    # Get keycode for the key
    if key not in KEYCODES:
        raise ValueError(f"Unknown key: {key}")
    keycode = KEYCODES[key]

    # Build modifier flags
    flags = 0
    for mod in modifiers:
        flags |= MODIFIER_FLAGS[mod]

    _press_key(keycode, flags)


def press_key(key: str) -> None:
    """Press a single key by name.

    Args:
        key: Key name like "return", "escape", "f1", "a".
    """
    lower = key.lower()
    if lower not in KEYCODES:
        raise ValueError(f"Unknown key: {key}")
    _press_key(KEYCODES[lower])
