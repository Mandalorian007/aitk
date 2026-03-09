"""Custom exceptions for mux module."""


class MuxError(Exception):
    """Base exception for mux operations."""

    pass


class TmuxNotFoundError(MuxError):
    """tmux is not installed."""

    pass


class SessionNotFoundError(MuxError):
    """tmux session does not exist."""

    pass


class SessionExistsError(MuxError):
    """tmux session already exists."""

    pass


class CommandTimeoutError(MuxError):
    """Command timed out waiting for completion."""

    pass


class TmuxCommandError(MuxError):
    """tmux subprocess command failed."""

    pass


class PatternError(MuxError):
    """Invalid regex pattern."""

    pass
