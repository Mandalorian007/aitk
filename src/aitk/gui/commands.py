"""macOS GUI automation CLI commands."""

import json
import sys
import tempfile
import time
from pathlib import Path

import click

from .errors import (
    GuiError,
    PlatformError,
    PermissionDeniedError,
    AppNotFoundError,
    WindowNotFoundError,
)

# Check platform before importing macOS-specific modules
if sys.platform != "darwin":

    @click.group()
    def group():
        """macOS GUI automation (macOS only - not available on this platform)."""
        pass

    @group.command()
    def init():
        """Check permissions and verify dependencies."""
        click.echo("Error: aitk gui requires macOS", err=True)
        sys.exit(1)

else:
    # Import macOS modules
    from . import screen, mouse, keyboard, apps, clipboard

    def _error_exit(msg: str, code: int = 1, ctx: click.Context | None = None) -> None:
        """Print error and exit, optionally showing help."""
        click.echo(f"Error: {msg}\n", err=True)
        if ctx:
            click.echo(ctx.get_help())
        sys.exit(code)

    @click.group()
    def group():
        """macOS GUI automation (macOS only).

        \b
        Desktop automation for AI agents using native macOS APIs.
        Requires macOS with Screen Recording and Accessibility permissions.

        \b
        NOTE: Use single quotes for arguments (e.g., 'text' not "text").
        Double quotes may cause issues with some CLI tools.

        \b
        RECOMMENDED WORKFLOW (Accessibility-first):
          1. aitk gui a11y APP      Inspect UI element tree
          2. aitk gui find APP X    Find elements by label
          3. aitk gui press APP BTN Press buttons by identifier
          4. aitk gui read APP      Read text values

        \b
        Accessibility APIs are preferred because they:
          - Provide semantic element info (roles, labels, values)
          - Work reliably regardless of visual state
          - Support direct button/control interaction
          - Don't require coordinate calculations

        \b
        FALLBACK (when accessibility unavailable):
          - aitk gui see + aitk gui ocr   Visual text extraction
          - aitk gui click X Y            Coordinate-based clicks

        \b
        Quick start:
          aitk gui init             Check permissions
          aitk gui a11y Calculator  Inspect Calculator UI
          aitk gui press Calc '5'   Press button '5'
          aitk gui read Calculator  Read display value
        """
        pass

    @group.command()
    def init():
        """Check permissions and verify dependencies.

        Tests Screen Recording and Accessibility permissions.
        Guides you to grant access if needed.

        \b
        Example:
          aitk gui init
        """
        click.echo("Checking macOS GUI automation...")
        click.echo()

        # Test screen recording
        click.echo("Screen Recording: ", nl=False)
        try:
            test_path = Path(tempfile.gettempdir()) / f"aitk-gui-test-{int(time.time())}.png"
            screen.capture_screen(test_path)
            test_path.unlink(missing_ok=True)
            click.echo("granted")
        except PermissionDeniedError:
            click.echo("NOT GRANTED")
            click.echo("  Grant: System Settings > Privacy & Security > Screen Recording > Terminal")

        # Test basic Quartz events (mouse/keyboard don't require special permissions on most systems)
        click.echo("Quartz Events: ", nl=False)
        try:
            from Quartz import CGEventCreateMouseEvent, kCGEventMouseMoved, CGPointMake, kCGMouseButtonLeft
            event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, CGPointMake(0, 0), kCGMouseButtonLeft)
            if event:
                click.echo("available")
            else:
                click.echo("unavailable")
        except Exception as e:
            click.echo(f"error: {e}")

        # Test accessibility permission
        click.echo("Accessibility: ", nl=False)
        try:
            from . import accessibility
            if accessibility.check_accessibility_permission():
                click.echo("granted")
            else:
                click.echo("NOT GRANTED")
                click.echo("  Grant: System Settings > Privacy & Security > Accessibility > Terminal")
        except Exception as e:
            click.echo(f"error: {e}")

        # Test OCR availability
        click.echo("Vision (OCR): ", nl=False)
        try:
            import Vision
            click.echo("available")
        except ImportError:
            click.echo("not installed (optional)")
            click.echo("  Install: uv pip install 'aitk[ocr]'")

        click.echo()
        click.echo("Ready. Run: aitk gui see")

    @group.command("see")
    @click.option("-o", "--output", type=click.Path(), help="Output path (default: /tmp/gui-<timestamp>.png)")
    @click.option("--display", type=int, help="Display index to capture (0-indexed)")
    @click.pass_context
    def see_cmd(ctx, output, display):
        """Screenshot screen or specific display.

        \b
        Examples:
          aitk gui see
          aitk gui see -o ~/Desktop/screenshot.png
          aitk gui see --display 1
        """
        try:
            if output:
                path = Path(output)
            else:
                path = Path(tempfile.gettempdir()) / f"gui-{int(time.time())}.png"

            result = screen.capture_screen(path, display_index=display)
            click.echo(f"Saved: {result}")
        except PermissionDeniedError as e:
            _error_exit(str(e), ctx=ctx)
        except ValueError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("click")
    @click.argument("x", type=int)
    @click.argument("y", type=int)
    @click.option("--right", is_flag=True, help="Right-click instead of left")
    @click.option("--double", is_flag=True, help="Double-click")
    @click.pass_context
    def click_cmd(ctx, x, y, right, double):
        """Click at screen coordinates (fallback).

        Prefer 'press' command for buttons when accessibility is available.
        Use coordinates only when elements lack accessibility support.

        \b
        Coordinates are global (across all displays).

        \b
        Examples:
          aitk gui click 500 300
          aitk gui click 500 300 --right
          aitk gui click 500 300 --double
        """
        try:
            button = "right" if right else "left"
            clicks = 2 if double else 1
            mouse.click(x, y, button=button, clicks=clicks)
            click.echo(f"Clicked: ({x}, {y})")
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("type")
    @click.argument("text")
    @click.option("--delay", type=float, default=0.02, help="Delay between keystrokes (seconds)")
    @click.pass_context
    def type_cmd(ctx, text, delay):
        """Type a text string.

        \b
        NOTE: Use single quotes for text arguments.

        \b
        Examples:
          aitk gui type 'hello world'
          aitk gui type 'slow typing' --delay 0.1
        """
        try:
            keyboard.type_text(text, delay=delay)
            click.echo(f"Typed: {text}")
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("hotkey")
    @click.argument("combo")
    @click.pass_context
    def hotkey_cmd(ctx, combo):
        """Execute a key combination.

        Use + to combine keys. Modifiers: cmd, ctrl, shift, option/alt.

        \b
        Examples:
          aitk gui hotkey cmd+c
          aitk gui hotkey cmd+shift+4
          aitk gui hotkey ctrl+option+esc
          aitk gui hotkey cmd+space
        """
        try:
            keyboard.hotkey(combo)
            click.echo(f"Pressed: {combo}")
        except ValueError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("apps")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    @click.pass_context
    def apps_cmd(ctx, as_json):
        """List running applications.

        \b
        Examples:
          aitk gui apps
          aitk gui apps --json
        """
        try:
            running = apps.get_running_apps()

            if as_json:
                click.echo(json.dumps(running, indent=2))
            else:
                for app in running:
                    marker = "*" if app["is_active"] else " "
                    click.echo(f"{marker} {app['name']} (pid: {app['pid']})")
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("screens")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    @click.pass_context
    def screens_cmd(ctx, as_json):
        """List monitors with geometry.

        \b
        Examples:
          aitk gui screens
          aitk gui screens --json
        """
        try:
            displays = screen.get_screens()

            if as_json:
                click.echo(json.dumps(displays, indent=2))
            else:
                for d in displays:
                    main = " (main)" if d["is_main"] else ""
                    click.echo(f"Display {d['index']}{main}: {d['width']}x{d['height']} at ({d['x']}, {d['y']})")
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("clipboard")
    @click.argument("text", required=False)
    @click.pass_context
    def clipboard_cmd(ctx, text):
        """Get or set clipboard text.

        Without argument, prints current clipboard.
        With argument, sets clipboard to that text.

        \b
        NOTE: Use single quotes for text arguments.

        \b
        Examples:
          aitk gui clipboard
          aitk gui clipboard 'text to copy'
        """
        try:
            if text is not None:
                clipboard.set_clipboard(text)
                click.echo(f"Clipboard set: {text[:50]}{'...' if len(text) > 50 else ''}")
            else:
                content = clipboard.get_clipboard()
                if content:
                    click.echo(content)
                else:
                    click.echo("(clipboard empty or not text)")
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    # Phase 2 commands

    @group.command("scroll")
    @click.argument("direction", type=click.Choice(["up", "down", "left", "right"]))
    @click.option("--amount", type=int, default=3, help="Scroll amount (default: 3)")
    @click.pass_context
    def scroll_cmd(ctx, direction, amount):
        """Scroll in a direction.

        \b
        Examples:
          aitk gui scroll down
          aitk gui scroll up --amount 5
        """
        try:
            mouse.scroll(direction, amount=amount)
            click.echo(f"Scrolled: {direction} ({amount})")
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("drag")
    @click.argument("x1", type=int)
    @click.argument("y1", type=int)
    @click.argument("x2", type=int)
    @click.argument("y2", type=int)
    @click.option("--duration", type=float, default=0.5, help="Drag duration in seconds")
    @click.pass_context
    def drag_cmd(ctx, x1, y1, x2, y2, duration):
        """Drag from one point to another.

        \b
        Examples:
          aitk gui drag 100 100 500 500
          aitk gui drag 100 100 500 500 --duration 1.0
        """
        try:
            mouse.drag(x1, y1, x2, y2, duration=duration)
            click.echo(f"Dragged: ({x1}, {y1}) -> ({x2}, {y2})")
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("focus")
    @click.argument("app_name")
    @click.pass_context
    def focus_cmd(ctx, app_name):
        """Bring an application to the foreground.

        \b
        NOTE: Use single quotes for app names with spaces.

        \b
        Examples:
          aitk gui focus Safari
          aitk gui focus 'Visual Studio Code'
        """
        try:
            result = apps.focus_app(app_name)
            click.echo(f"Focused: {result['name']}")
        except AppNotFoundError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("window")
    @click.argument("app_name")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    @click.pass_context
    def window_cmd(ctx, app_name, as_json):
        """Get window bounds and info for an application.

        \b
        Examples:
          aitk gui window Safari
          aitk gui window Safari --json
        """
        try:
            info = apps.get_window_info(app_name)

            if as_json:
                click.echo(json.dumps(info, indent=2))
            else:
                click.echo(f"{info['name']}: {info['title']}")
                click.echo(f"  Position: ({info['x']}, {info['y']})")
                click.echo(f"  Size: {info['width']}x{info['height']}")
        except (AppNotFoundError, WindowNotFoundError) as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    # OCR (fallback when accessibility not available)

    @group.command("ocr")
    @click.option("--path", type=click.Path(exists=True), help="Image file to OCR (default: capture screen)")
    @click.option("--display", type=int, help="Display index to capture (if no --path)")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON with coordinates")
    @click.pass_context
    def ocr_cmd(ctx, path, display, as_json):
        """Extract text from screen or image file (fallback).

        NOTE: Prefer accessibility commands (a11y, find, read) when possible.
        OCR is a fallback for apps without accessibility support.

        \b
        Uses macOS Vision framework for text recognition.
        Returns text with bounding box coordinates.

        \b
        Examples:
          aitk gui ocr
          aitk gui ocr --path screenshot.png
          aitk gui ocr --json
        """
        try:
            from . import ocr

            if path:
                results = ocr.ocr_image(path)
            else:
                results = ocr.ocr_screen(display_index=display)

            if as_json:
                click.echo(json.dumps(results, indent=2))
            else:
                for r in results:
                    click.echo(f"{r['text']}")
        except FileNotFoundError as e:
            _error_exit(str(e), ctx=ctx)
        except PermissionDeniedError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)
        except Exception as e:
            _error_exit(f"OCR failed: {e}", ctx=ctx)

    # Accessibility (preferred approach)

    @group.command("a11y")
    @click.argument("app_name")
    @click.option("--depth", type=int, default=10, help="Maximum tree depth (default: 10)")
    @click.pass_context
    def a11y_cmd(ctx, app_name, depth):
        """Dump accessibility tree for an application (preferred).

        Start here to understand an app's UI structure. Shows element
        hierarchy with roles, identifiers, titles, and values.

        \b
        Use this to discover button identifiers for 'press' command
        and element structure for 'find' and 'read' commands.

        \b
        Examples:
          aitk gui a11y Calculator
          aitk gui a11y Safari --depth 5
        """
        try:
            from . import accessibility

            tree = accessibility.get_app_accessibility_tree(app_name, max_depth=depth)
            click.echo(json.dumps(tree, indent=2))
        except PermissionDeniedError as e:
            _error_exit(str(e), ctx=ctx)
        except AppNotFoundError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("find")
    @click.argument("app_name")
    @click.argument("label")
    @click.option("--max", "max_results", type=int, default=10, help="Maximum results (default: 10)")
    @click.pass_context
    def find_cmd(ctx, app_name, label, max_results):
        """Find UI elements by label/title/value (preferred).

        Searches the accessibility tree for elements matching the label.
        Use to locate buttons, text fields, and other controls.

        \b
        NOTE: Use single quotes for label arguments.

        \b
        Examples:
          aitk gui find Calculator 'Equals'
          aitk gui find Safari 'URL'
          aitk gui find Notes 'New Note'
        """
        try:
            from . import accessibility

            results = accessibility.find_elements(app_name, label, max_results=max_results)

            if not results:
                click.echo(f"No elements found matching: {label}")
            else:
                click.echo(json.dumps(results, indent=2))
        except PermissionDeniedError as e:
            _error_exit(str(e), ctx=ctx)
        except AppNotFoundError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("read")
    @click.argument("app_name")
    @click.option("--role", help="Element role to match (e.g., AXStaticText)")
    @click.option("--title", help="Element title to match")
    @click.pass_context
    def read_cmd(ctx, app_name, role, title):
        """Read value from a UI element (preferred).

        Returns the value/text of the first matching element.
        Use to read displays, labels, text fields, and status text.

        \b
        Examples:
          aitk gui read Calculator --role AXStaticText
          aitk gui read Safari --title "URL"
          aitk gui read Notes --role AXTextArea
        """
        try:
            from . import accessibility

            value = accessibility.get_element_value(app_name, role=role, title=title)

            if value is not None:
                click.echo(value)
            else:
                click.echo("(no value found)")
        except PermissionDeniedError as e:
            _error_exit(str(e), ctx=ctx)
        except AppNotFoundError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("wait")
    @click.argument("app_name")
    @click.argument("text")
    @click.option("-t", "--timeout", type=float, default=30, help="Timeout in seconds (default: 30)")
    @click.option("-i", "--interval", type=float, default=0.5, help="Poll interval (default: 0.5)")
    @click.pass_context
    def wait_cmd(ctx, app_name, text, timeout, interval):
        """Wait for text to appear in an application.

        Polls the accessibility tree until the text is found or timeout.
        Useful for waiting on UI state changes.

        \b
        NOTE: Use single quotes for text arguments.

        \b
        Examples:
          aitk gui wait Calculator '78'
          aitk gui wait Safari 'Page loaded' -t 60
        """
        import time as time_module

        try:
            from . import accessibility

            start = time_module.monotonic()
            deadline = start + timeout

            while time_module.monotonic() < deadline:
                try:
                    results = accessibility.find_elements(app_name, text, max_results=1)
                    if results:
                        elapsed = time_module.monotonic() - start
                        click.echo(f"Found after {elapsed:.1f}s: {text}")
                        click.echo(json.dumps(results[0], indent=2))
                        return
                except GuiError:
                    pass  # App might not be ready yet

                time_module.sleep(interval)

            _error_exit(f"Timeout waiting for: {text}", ctx=ctx)
        except PermissionDeniedError as e:
            _error_exit(str(e), ctx=ctx)
        except AppNotFoundError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)

    @group.command("press")
    @click.argument("app_name")
    @click.argument("button")
    @click.pass_context
    def press_cmd(ctx, app_name, button):
        """Press a button by identifier (preferred over click).

        Finds a button by identifier/description/title and triggers it
        via accessibility API. More reliable than coordinate clicks.

        \b
        Use 'aitk gui a11y APP' to discover button identifiers.

        \b
        NOTE: Use single quotes for button arguments.

        \b
        Examples:
          aitk gui press Calculator 'Equals'
          aitk gui press Calculator 'Five'
          aitk gui press Safari 'Back'
        """
        try:
            from . import accessibility

            accessibility.press_button(app_name, button)
            click.echo(f"Pressed: {button}")
        except PermissionDeniedError as e:
            _error_exit(str(e), ctx=ctx)
        except AppNotFoundError as e:
            _error_exit(str(e), ctx=ctx)
        except GuiError as e:
            _error_exit(str(e), ctx=ctx)
