"""Low-level tmux subprocess wrapper."""

import subprocess
from typing import Optional

from .errors import (
    TmuxNotFoundError,
    SessionNotFoundError,
    SessionExistsError,
    TmuxCommandError,
)

# Timeout for tmux subprocess calls (prevents hangs on broken tmux state)
TMUX_SUBPROCESS_TIMEOUT = 10


def _run_tmux(
    *args: str, check: bool = True, capture: bool = True
) -> subprocess.CompletedProcess:
    """Run a tmux command with timeout protection."""
    cmd = ["tmux", *args]
    try:
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=TMUX_SUBPROCESS_TIMEOUT,
            check=check,
        )
    except subprocess.TimeoutExpired as e:
        raise TmuxCommandError(f"tmux command timed out: {' '.join(cmd)}") from e
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ""
        raise TmuxCommandError(f"tmux command failed: {stderr}") from e
    except FileNotFoundError:
        raise TmuxNotFoundError("tmux is not installed")


def check_installed() -> bool:
    """Check if tmux is installed."""
    try:
        _run_tmux("-V")
        return True
    except TmuxNotFoundError:
        return False
    except TmuxCommandError:
        return True  # tmux exists but command failed for other reasons


def get_version() -> str:
    """Get tmux version string."""
    result = _run_tmux("-V")
    return result.stdout.strip()


def session_exists(name: str) -> bool:
    """Check if a session exists."""
    result = _run_tmux("has-session", "-t", name, check=False)
    return result.returncode == 0


def create_session(name: str) -> None:
    """Create a new detached session."""
    if session_exists(name):
        raise SessionExistsError(f"Session '{name}' already exists")
    _run_tmux("new-session", "-d", "-s", name)


def kill_session(name: str) -> None:
    """Kill a session."""
    if not session_exists(name):
        raise SessionNotFoundError(f"Session '{name}' not found")
    _run_tmux("kill-session", "-t", name)


def list_sessions() -> list[dict]:
    """List all sessions with metadata."""
    result = _run_tmux(
        "list-sessions",
        "-F",
        "#{session_name}\t#{session_created}\t#{session_windows}",
        check=False,
    )
    if result.returncode != 0:
        # No sessions exist
        return []

    sessions = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            sessions.append(
                {
                    "name": parts[0],
                    "created": int(parts[1]),
                    "windows": int(parts[2]),
                }
            )
    return sessions


def send_keys(name: str, keys: str, enter: bool = False) -> None:
    """Send keystrokes to a session."""
    if not session_exists(name):
        raise SessionNotFoundError(f"Session '{name}' not found")

    _run_tmux("send-keys", "-t", name, keys)
    if enter:
        _run_tmux("send-keys", "-t", name, "Enter")


def capture_pane(name: str, start: Optional[int] = None, end: Optional[int] = None) -> str:
    """Capture pane output."""
    if not session_exists(name):
        raise SessionNotFoundError(f"Session '{name}' not found")

    args = ["capture-pane", "-t", name, "-p"]
    if start is not None:
        args.extend(["-S", str(start)])
    if end is not None:
        args.extend(["-E", str(end)])

    result = _run_tmux(*args)
    return result.stdout
