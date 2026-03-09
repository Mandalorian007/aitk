"""tmux automation CLI commands."""

import json
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import click

from . import tmux, sentinel
from .errors import (
    MuxError,
    TmuxNotFoundError,
    SessionNotFoundError,
    SessionExistsError,
    CommandTimeoutError,
    PatternError,
)


def _error_exit(msg: str, code: int = 1, ctx: click.Context | None = None) -> None:
    """Print error and exit, optionally showing help."""
    click.echo(f"Error: {msg}\n", err=True)
    if ctx:
        click.echo(ctx.get_help())
    sys.exit(code)


@click.group()
def group():
    """tmux session automation.

    \b
    Commands for managing tmux sessions with reliable command execution
    and output capture using sentinel-based completion detection.

    \b
    Quick start:
      aitk mux init              Verify tmux is installed
      aitk mux create mydev      Create a session
      aitk mux run mydev 'ls'    Run command, wait for output
      aitk mux kill mydev        Clean up
    """
    pass


@group.command()
@click.pass_context
def init(ctx):
    """Verify tmux is installed.

    \b
    Example:
      aitk mux init
    """
    try:
        if tmux.check_installed():
            version = tmux.get_version()
            click.echo(f"tmux: installed ({version})")
        else:
            _error_exit("tmux is not installed", ctx=ctx)
    except TmuxNotFoundError:
        _error_exit("tmux is not installed", ctx=ctx)
    except MuxError as e:
        _error_exit(str(e), ctx=ctx)


@group.command()
@click.argument("name")
@click.pass_context
def create(ctx, name):
    """Create a detached tmux session.

    \b
    Example:
      aitk mux create myproject
    """
    try:
        tmux.create_session(name)
        click.echo(f"Created session: {name}")
    except SessionExistsError:
        _error_exit(f"Session '{name}' already exists", ctx=ctx)
    except MuxError as e:
        _error_exit(str(e), ctx=ctx)


@group.command()
@click.argument("name")
@click.pass_context
def kill(ctx, name):
    """Kill a tmux session.

    \b
    Example:
      aitk mux kill myproject
    """
    try:
        tmux.kill_session(name)
        click.echo(f"Killed session: {name}")
    except SessionNotFoundError:
        _error_exit(f"Session '{name}' not found", ctx=ctx)
    except MuxError as e:
        _error_exit(str(e), ctx=ctx)


@group.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def list_sessions(ctx, as_json):
    """List all tmux sessions.

    \b
    Examples:
      aitk mux list
      aitk mux list --json
    """
    try:
        sessions = tmux.list_sessions()

        if as_json:
            click.echo(json.dumps({"sessions": sessions}, indent=2))
        elif not sessions:
            click.echo("No sessions")
        else:
            for s in sessions:
                click.echo(f"{s['name']} ({s['windows']} windows)")
    except MuxError as e:
        _error_exit(str(e), ctx=ctx)


@group.command()
@click.argument("name")
@click.argument("cmd")
@click.option("-t", "--timeout", default=60, help="Timeout in seconds (default: 60)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON with exit code")
@click.pass_context
def run(ctx, name, cmd, timeout, as_json):
    """Run a command and wait for completion.

    Uses sentinel-based detection to reliably capture output and exit code.
    Command is wrapped with markers to detect when it finishes.

    NOTE: Use single quotes for text arguments.

    \b
    Examples:
      aitk mux run mydev 'echo hello'
      aitk mux run mydev 'make build' -t 300
      aitk mux run mydev 'exit 42' --json
    """
    try:
        result = sentinel.run_command(name, cmd, timeout=float(timeout))

        if as_json:
            click.echo(
                json.dumps(
                    {
                        "output": result.output,
                        "exit_code": result.exit_code,
                        "elapsed": round(result.elapsed, 3),
                    },
                    indent=2,
                )
            )
        else:
            if result.output:
                click.echo(result.output)
            if result.exit_code != 0:
                sys.exit(result.exit_code)
    except SessionNotFoundError:
        _error_exit(f"Session '{name}' not found", ctx=ctx)
    except CommandTimeoutError as e:
        _error_exit(str(e), ctx=ctx)
    except MuxError as e:
        _error_exit(str(e), ctx=ctx)


@group.command()
@click.argument("name")
@click.argument("text")
@click.option("--enter", is_flag=True, help="Press Enter after sending")
@click.pass_context
def send(ctx, name, text, enter):
    """Send raw keystrokes to a session.

    Does not wait for command completion. Use this for interactive
    programs or when you don't need to capture output.

    NOTE: Use single quotes for text arguments.

    \b
    Examples:
      aitk mux send mydev 'cd /tmp'
      aitk mux send mydev 'npm start' --enter
    """
    try:
        tmux.send_keys(name, text, enter=enter)
    except SessionNotFoundError:
        _error_exit(f"Session '{name}' not found", ctx=ctx)
    except MuxError as e:
        _error_exit(str(e), ctx=ctx)


@group.command()
@click.argument("name")
@click.option("-n", "--lines", default=1000, help="Number of lines to capture")
@click.pass_context
def logs(ctx, name, lines):
    """Capture pane output from a session.

    \b
    Examples:
      aitk mux logs mydev
      aitk mux logs mydev -n 50
    """
    try:
        output = tmux.capture_pane(name, start=-lines)
        click.echo(output.rstrip())
    except SessionNotFoundError:
        _error_exit(f"Session '{name}' not found", ctx=ctx)
    except MuxError as e:
        _error_exit(str(e), ctx=ctx)


@group.command()
@click.argument("name")
@click.argument("pattern")
@click.option("-t", "--timeout", default=300, help="Timeout in seconds (default: 300)")
@click.option(
    "-i", "--interval", default=1.0, help="Poll interval in seconds (default: 1)"
)
@click.pass_context
def poll(ctx, name, pattern, timeout, interval):
    """Wait for a regex pattern to appear in pane output.

    Useful for waiting on async processes like servers starting up
    or long-running builds completing.

    NOTE: Use single quotes for text arguments.

    \b
    Examples:
      aitk mux poll mydev 'Server ready' -t 60
      aitk mux poll mydev 'BUILD (SUCCESS|FAILED)' -t 600
    """
    # Validate regex pattern
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        _error_exit(f"Invalid regex pattern: {e}", ctx=ctx)
        return  # for type checker

    try:
        if not tmux.session_exists(name):
            _error_exit(f"Session '{name}' not found", ctx=ctx)

        start_time = time.monotonic()
        deadline = start_time + float(timeout)

        while time.monotonic() < deadline:
            output = tmux.capture_pane(name, start=-1000)
            match = compiled.search(output)

            if match:
                elapsed = time.monotonic() - start_time
                click.echo(f"Pattern matched after {elapsed:.1f}s: {match.group()}")
                return

            time.sleep(float(interval))

        elapsed = time.monotonic() - start_time
        _error_exit(f"Pattern not found after {elapsed:.1f}s", ctx=ctx)
    except SessionNotFoundError:
        _error_exit(f"Session '{name}' not found", ctx=ctx)
    except MuxError as e:
        _error_exit(str(e), ctx=ctx)


@group.command()
@click.argument("cmd")
@click.option("-n", "--count", default=3, help="Number of parallel sessions (default: 3)")
@click.option("-t", "--timeout", default=300, help="Timeout per command in seconds (default: 300)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def fanout(ctx, cmd, count, timeout, as_json):
    """Run a command in parallel across ephemeral sessions.

    Creates temporary sessions, runs the command in each, collects
    output, and cleans up automatically.

    NOTE: Use single quotes for text arguments.

    \b
    Examples:
      aitk mux fanout 'echo $RANDOM' --count 3
      aitk mux fanout 'hostname' -n 5 --json
    """
    prefix = f"aitk-fanout-{uuid.uuid4().hex[:8]}"
    session_names = [f"{prefix}-{i}" for i in range(count)]

    def run_in_session(session_name: str) -> dict:
        """Create session, run command, return result."""
        try:
            tmux.create_session(session_name)
            result = sentinel.run_command(session_name, cmd, timeout=float(timeout))
            return {
                "session": session_name,
                "output": result.output,
                "exit_code": result.exit_code,
                "elapsed": round(result.elapsed, 3),
                "error": None,
            }
        except Exception as e:
            return {
                "session": session_name,
                "output": None,
                "exit_code": -1,
                "elapsed": 0,
                "error": str(e),
            }

    results = []
    try:
        # Run in parallel
        with ThreadPoolExecutor(max_workers=count) as executor:
            futures = {
                executor.submit(run_in_session, name): name for name in session_names
            }
            for future in as_completed(futures):
                results.append(future.result())

        # Sort by session name for consistent output
        results.sort(key=lambda r: r["session"])

        if as_json:
            click.echo(json.dumps({"results": results}, indent=2))
        else:
            for r in results:
                click.echo(f"--- {r['session']} ---")
                if r["error"]:
                    click.echo(f"Error: {r['error']}")
                else:
                    if r["output"]:
                        click.echo(r["output"])
                    if r["exit_code"] != 0:
                        click.echo(f"(exit code: {r['exit_code']})")
                click.echo()

    finally:
        # Always clean up sessions
        for name in session_names:
            try:
                if tmux.session_exists(name):
                    tmux.kill_session(name)
            except MuxError:
                pass  # Best effort cleanup
