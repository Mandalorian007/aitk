"""Custom exceptions for gui module."""

import sys


class GuiError(Exception):
    """Base exception for gui operations."""

    pass


class PlatformError(GuiError):
    """Not running on macOS."""

    pass


class PermissionDeniedError(GuiError):
    """Missing required macOS permission."""

    pass


class AppNotFoundError(GuiError):
    """Application not found."""

    pass


class WindowNotFoundError(GuiError):
    """Window not found for application."""

    pass


def require_macos() -> None:
    """Raise PlatformError if not on macOS."""
    if sys.platform != "darwin":
        raise PlatformError("aitk gui requires macOS")
