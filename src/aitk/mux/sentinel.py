"""Sentinel-based command completion detection."""

import re
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from . import tmux
from .errors import CommandTimeoutError, SessionNotFoundError


@dataclass
class CommandResult:
    """Result of a sentinel-wrapped command execution."""

    output: str
    exit_code: int
    elapsed: float


def generate_token() -> str:
    """Generate a unique sentinel token."""
    return uuid.uuid4().hex[:12]


def wrap_command(cmd: str, token: str) -> str:
    """Wrap a command with sentinel markers.

    Format: echo "__START_<token>" ; <cmd> ; echo "__DONE_<token>:$?"

    This allows us to:
    1. Detect when the command starts
    2. Capture all output between markers
    3. Get the exit code
    """
    return f'echo "__START_{token}" ; {cmd} ; echo "__DONE_{token}:$?"'


def parse_output(pane_content: str, token: str) -> Optional[tuple[str, int]]:
    """Parse pane content looking for completed command output.

    Returns (output, exit_code) if command completed, None otherwise.

    The markers appear twice in the pane:
    1. When the command is echoed (as typed)
    2. When echo actually executes and outputs the marker on its own line

    We look for the marker on its own line (the actual output), not the echoed command.
    """
    start_marker = f"__START_{token}"
    done_pattern = rf"^__DONE_{token}:(\d+)$"

    # Split into lines for easier processing
    lines = pane_content.split("\n")

    # Find the START marker as its own line (output from echo, not the command)
    start_line_idx = None
    for i, line in enumerate(lines):
        if line.strip() == start_marker:
            start_line_idx = i
            break

    if start_line_idx is None:
        return None

    # Find the DONE marker as its own line after the start
    done_line_idx = None
    exit_code = None
    for i in range(start_line_idx + 1, len(lines)):
        match = re.match(done_pattern, lines[i].strip())
        if match:
            done_line_idx = i
            exit_code = int(match.group(1))
            break

    if done_line_idx is None or exit_code is None:
        return None

    # Extract output between markers (excluding the marker lines themselves)
    output_lines = lines[start_line_idx + 1 : done_line_idx]

    # Strip leading/trailing empty lines
    while output_lines and not output_lines[0].strip():
        output_lines.pop(0)
    while output_lines and not output_lines[-1].strip():
        output_lines.pop()

    output = "\n".join(output_lines)

    return output, exit_code


def run_command(
    session: str,
    cmd: str,
    timeout: float = 60.0,
    poll_interval: float = 0.1,
) -> CommandResult:
    """Run a command with sentinel-based completion detection.

    Args:
        session: tmux session name
        cmd: Command to execute
        timeout: Maximum time to wait for completion (seconds)
        poll_interval: How often to check for completion (seconds)

    Returns:
        CommandResult with output, exit code, and elapsed time

    Raises:
        SessionNotFoundError: Session doesn't exist
        CommandTimeoutError: Command didn't complete within timeout
    """
    if not tmux.session_exists(session):
        raise SessionNotFoundError(f"Session '{session}' not found")

    token = generate_token()
    wrapped_cmd = wrap_command(cmd, token)

    # Send the wrapped command
    tmux.send_keys(session, wrapped_cmd, enter=True)

    # Poll for completion
    start_time = time.monotonic()
    deadline = start_time + timeout

    while time.monotonic() < deadline:
        pane_content = tmux.capture_pane(session, start=-1000)
        result = parse_output(pane_content, token)

        if result is not None:
            output, exit_code = result
            elapsed = time.monotonic() - start_time
            return CommandResult(output=output, exit_code=exit_code, elapsed=elapsed)

        time.sleep(poll_interval)

    elapsed = time.monotonic() - start_time
    raise CommandTimeoutError(
        f"Command timed out after {elapsed:.1f}s waiting for completion"
    )
