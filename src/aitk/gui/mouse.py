"""Mouse control using Quartz CoreGraphics."""

from .errors import require_macos

require_macos()

from Quartz import (
    CGEventCreateMouseEvent,
    CGEventPost,
    CGEventSetIntegerValueField,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGEventRightMouseDown,
    kCGEventRightMouseUp,
    kCGEventLeftMouseDragged,
    kCGEventScrollWheel,
    kCGHIDEventTap,
    kCGMouseButtonLeft,
    kCGMouseButtonRight,
    kCGScrollWheelEventDeltaAxis1,
    kCGScrollWheelEventDeltaAxis2,
    CGPointMake,
)
import time


def click(x: int, y: int, button: str = "left", clicks: int = 1) -> None:
    """Click at coordinates.

    Args:
        x: X coordinate.
        y: Y coordinate.
        button: "left" or "right".
        clicks: Number of clicks (1 for single, 2 for double).
    """
    point = CGPointMake(float(x), float(y))

    if button == "right":
        down_type = kCGEventRightMouseDown
        up_type = kCGEventRightMouseUp
        mouse_button = kCGMouseButtonRight
    else:
        down_type = kCGEventLeftMouseDown
        up_type = kCGEventLeftMouseUp
        mouse_button = kCGMouseButtonLeft

    for click_num in range(clicks):
        down_event = CGEventCreateMouseEvent(None, down_type, point, mouse_button)
        up_event = CGEventCreateMouseEvent(None, up_type, point, mouse_button)

        if clicks > 1:
            CGEventSetIntegerValueField(down_event, 1, click_num + 1)
            CGEventSetIntegerValueField(up_event, 1, click_num + 1)

        CGEventPost(kCGHIDEventTap, down_event)
        CGEventPost(kCGHIDEventTap, up_event)

        if click_num < clicks - 1:
            time.sleep(0.05)


def double_click(x: int, y: int) -> None:
    """Double-click at coordinates."""
    click(x, y, clicks=2)


def right_click(x: int, y: int) -> None:
    """Right-click at coordinates."""
    click(x, y, button="right")


def drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> None:
    """Drag from one point to another.

    Args:
        x1, y1: Start coordinates.
        x2, y2: End coordinates.
        duration: Time in seconds for the drag operation.
    """
    start = CGPointMake(float(x1), float(y1))
    end = CGPointMake(float(x2), float(y2))

    down_event = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, start, kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, down_event)

    steps = max(int(duration * 60), 10)
    for i in range(1, steps + 1):
        t = i / steps
        current_x = x1 + (x2 - x1) * t
        current_y = y1 + (y2 - y1) * t
        current = CGPointMake(current_x, current_y)

        drag_event = CGEventCreateMouseEvent(None, kCGEventLeftMouseDragged, current, kCGMouseButtonLeft)
        CGEventPost(kCGHIDEventTap, drag_event)
        time.sleep(duration / steps)

    up_event = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, end, kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, up_event)


def scroll(direction: str, amount: int = 3) -> None:
    """Scroll in a direction.

    Args:
        direction: "up", "down", "left", or "right".
        amount: Number of scroll units.
    """
    scroll_event = CGEventCreateMouseEvent(None, kCGEventScrollWheel, CGPointMake(0, 0), 0)

    if direction == "up":
        CGEventSetIntegerValueField(scroll_event, kCGScrollWheelEventDeltaAxis1, amount)
    elif direction == "down":
        CGEventSetIntegerValueField(scroll_event, kCGScrollWheelEventDeltaAxis1, -amount)
    elif direction == "left":
        CGEventSetIntegerValueField(scroll_event, kCGScrollWheelEventDeltaAxis2, amount)
    elif direction == "right":
        CGEventSetIntegerValueField(scroll_event, kCGScrollWheelEventDeltaAxis2, -amount)
    else:
        raise ValueError(f"Invalid direction: {direction}. Use up/down/left/right.")

    CGEventPost(kCGHIDEventTap, scroll_event)
