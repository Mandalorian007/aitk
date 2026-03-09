"""Screen capture and display information using Quartz/AppKit."""

from pathlib import Path

from .errors import require_macos, PermissionDeniedError

require_macos()

from Quartz import (
    CGWindowListCreateImage,
    CGRectNull,
    CGRectMake,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    kCGWindowImageDefault,
    CGMainDisplayID,
    CGDisplayBounds,
    CGGetActiveDisplayList,
)
from AppKit import NSScreen, NSBitmapImageRep, NSPNGFileType


def get_screens() -> list[dict]:
    """Get list of all screens with their geometry.

    Returns:
        List of dicts with index, x, y, width, height, is_main keys.
    """
    screens = []
    for i, screen in enumerate(NSScreen.screens()):
        frame = screen.frame()
        screens.append({
            "index": i,
            "x": int(frame.origin.x),
            "y": int(frame.origin.y),
            "width": int(frame.size.width),
            "height": int(frame.size.height),
            "is_main": screen == NSScreen.mainScreen(),
        })
    return screens


def get_display_ids() -> list[int]:
    """Get list of CGDisplayIDs for all active displays."""
    max_displays = 16
    err, display_ids, count = CGGetActiveDisplayList(max_displays, None, None)
    if err != 0:
        return [CGMainDisplayID()]
    return list(display_ids[:count])


def capture_screen(output_path: Path, display_index: int | None = None) -> Path:
    """Capture screenshot of screen to file.

    Args:
        output_path: Where to save the PNG file.
        display_index: Which display to capture (0-indexed). None for all displays.

    Returns:
        Path to saved file.

    Raises:
        PermissionDeniedError: If screen recording permission not granted.
    """
    if display_index is not None:
        display_ids = get_display_ids()
        if display_index >= len(display_ids):
            raise ValueError(f"Display index {display_index} out of range (have {len(display_ids)} displays)")
        display_id = display_ids[display_index]
        bounds = CGDisplayBounds(display_id)
        rect = CGRectMake(bounds.origin.x, bounds.origin.y, bounds.size.width, bounds.size.height)
    else:
        rect = CGRectNull

    image = CGWindowListCreateImage(
        rect,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        kCGWindowImageDefault,
    )

    if image is None:
        raise PermissionDeniedError(
            "Screen Recording permission required.\n"
            "Grant access: System Settings > Privacy & Security > Screen Recording > Terminal"
        )

    bitmap = NSBitmapImageRep.alloc().initWithCGImage_(image)
    png_data = bitmap.representationUsingType_properties_(NSPNGFileType, None)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    png_data.writeToFile_atomically_(str(output_path), True)

    return output_path
