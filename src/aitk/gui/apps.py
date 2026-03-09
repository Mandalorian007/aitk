"""Application management using AppKit."""

from .errors import require_macos, AppNotFoundError, WindowNotFoundError

require_macos()

from AppKit import NSWorkspace, NSRunningApplication
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    kCGWindowOwnerPID,
    kCGWindowBounds,
    kCGWindowOwnerName,
    kCGWindowName,
    kCGWindowLayer,
)


def get_running_apps() -> list[dict]:
    """Get list of running applications.

    Returns:
        List of dicts with name, pid, bundle_id, is_active keys.
    """
    workspace = NSWorkspace.sharedWorkspace()
    active = workspace.frontmostApplication()
    active_pid = active.processIdentifier() if active else None

    apps = []
    for app in workspace.runningApplications():
        # Skip background-only apps
        if app.activationPolicy() != 0:  # NSApplicationActivationPolicyRegular = 0
            continue

        name = app.localizedName()
        if not name:
            continue

        apps.append({
            "name": name,
            "pid": app.processIdentifier(),
            "bundle_id": app.bundleIdentifier() or "",
            "is_active": app.processIdentifier() == active_pid,
        })

    return sorted(apps, key=lambda a: a["name"].lower())


def get_frontmost_app() -> dict | None:
    """Get the currently active application.

    Returns:
        Dict with name, pid, bundle_id keys, or None.
    """
    workspace = NSWorkspace.sharedWorkspace()
    app = workspace.frontmostApplication()
    if not app:
        return None

    return {
        "name": app.localizedName(),
        "pid": app.processIdentifier(),
        "bundle_id": app.bundleIdentifier() or "",
    }


def focus_app(name: str) -> dict:
    """Bring an application to the foreground.

    Args:
        name: Application name (case-insensitive partial match).

    Returns:
        Dict with name, pid, bundle_id of focused app.

    Raises:
        AppNotFoundError: If no matching app is found.
    """
    workspace = NSWorkspace.sharedWorkspace()
    name_lower = name.lower()

    # Try exact match first, then prefix, then contains
    for match_fn in [
        lambda n: n.lower() == name_lower,
        lambda n: n.lower().startswith(name_lower),
        lambda n: name_lower in n.lower(),
    ]:
        for app in workspace.runningApplications():
            if app.activationPolicy() != 0:
                continue
            app_name = app.localizedName()
            if app_name and match_fn(app_name):
                app.activateWithOptions_(0)
                return {
                    "name": app_name,
                    "pid": app.processIdentifier(),
                    "bundle_id": app.bundleIdentifier() or "",
                }

    raise AppNotFoundError(f"Application not found: {name}")


def get_window_info(app_name: str) -> dict:
    """Get window bounds and info for an application.

    Args:
        app_name: Application name (case-insensitive partial match).

    Returns:
        Dict with name, title, x, y, width, height keys.

    Raises:
        AppNotFoundError: If no matching app is found.
        WindowNotFoundError: If app has no visible windows.
    """
    workspace = NSWorkspace.sharedWorkspace()
    name_lower = app_name.lower()

    # Find the app
    target_pid = None
    target_name = None

    for match_fn in [
        lambda n: n.lower() == name_lower,
        lambda n: n.lower().startswith(name_lower),
        lambda n: name_lower in n.lower(),
    ]:
        for app in workspace.runningApplications():
            if app.activationPolicy() != 0:
                continue
            n = app.localizedName()
            if n and match_fn(n):
                target_pid = app.processIdentifier()
                target_name = n
                break
        if target_pid:
            break

    if not target_pid:
        raise AppNotFoundError(f"Application not found: {app_name}")

    # Get windows for this app
    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)

    for window in windows:
        if window.get(kCGWindowOwnerPID) != target_pid:
            continue
        if window.get(kCGWindowLayer, 0) != 0:
            continue  # Skip non-standard windows

        bounds = window.get(kCGWindowBounds, {})
        return {
            "name": target_name,
            "title": window.get(kCGWindowName, ""),
            "x": int(bounds.get("X", 0)),
            "y": int(bounds.get("Y", 0)),
            "width": int(bounds.get("Width", 0)),
            "height": int(bounds.get("Height", 0)),
        }

    raise WindowNotFoundError(f"No visible window found for: {target_name}")
