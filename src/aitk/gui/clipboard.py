"""Clipboard access using AppKit NSPasteboard."""

from .errors import require_macos

require_macos()

from AppKit import NSPasteboard, NSPasteboardTypeString


def get_clipboard() -> str | None:
    """Get text from clipboard.

    Returns:
        Clipboard text, or None if clipboard is empty or not text.
    """
    pasteboard = NSPasteboard.generalPasteboard()
    return pasteboard.stringForType_(NSPasteboardTypeString)


def set_clipboard(text: str) -> None:
    """Set clipboard text.

    Args:
        text: Text to copy to clipboard.
    """
    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, NSPasteboardTypeString)
