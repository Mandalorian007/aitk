"""Browser automation - Playwright."""

import asyncio
import glob
import json
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time
from functools import wraps
from pathlib import Path

import click

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

DEFAULT_PORT = 9222


def _run_async(f):
    """Run async function synchronously."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


def _check_chromium() -> tuple[bool, str]:
    """Check if Playwright Chromium is installed."""
    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        cache = home / "Library/Caches/ms-playwright"
        pattern = "chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"
    elif system == "Windows":
        cache = home / "AppData/Local/ms-playwright"
        pattern = "chromium-*/chrome-win/chrome.exe"
    else:
        cache = home / ".cache/ms-playwright"
        pattern = "chromium-*/chrome-linux/chrome"

    paths = sorted(glob.glob(str(cache / pattern)), reverse=True)
    return (True, paths[0]) if paths else (False, str(cache))


def _is_port_in_use(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("localhost", port)) == 0
    sock.close()
    return result


def _kill_port(port: int) -> bool:
    try:
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            import os
            for pid in result.stdout.strip().split('\n'):
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except (ValueError, ProcessLookupError):
                    pass
            return True
    except Exception:
        pass
    return False


def _ensure_init() -> str:
    """Check browser is initialized, return chromium path or exit."""
    if not PLAYWRIGHT_AVAILABLE:
        click.echo("Error: Playwright not installed", err=True)
        click.echo("Run: aitk browser init", err=True)
        sys.exit(1)

    installed, path = _check_chromium()
    if not installed:
        click.echo("Error: Chromium not installed", err=True)
        click.echo("Run: aitk browser init", err=True)
        sys.exit(1)

    return path


async def _connect(port: int):
    """Connect to browser, return (playwright, browser)."""
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        return pw, browser
    except Exception as e:
        await pw.stop()
        raise RuntimeError(f"Cannot connect to port {port}: {e}")


async def _get_page(browser):
    """Get active page."""
    contexts = browser.contexts
    if not contexts or not contexts[0].pages:
        raise RuntimeError("No pages found")
    return contexts[0].pages[-1]


@click.group()
def group():
    """Browser automation with Playwright."""
    pass


@group.command()
@_run_async
async def init():
    """Install Playwright and Chromium."""
    if PLAYWRIGHT_AVAILABLE:
        click.echo("Playwright: installed")
    else:
        click.echo("Installing Playwright...")
        result = subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], capture_output=True, text=True)
        if result.returncode != 0:
            click.echo(f"Error: {result.stderr}", err=True)
            sys.exit(1)
        click.echo("Playwright: installed")

    installed, path = _check_chromium()
    if installed:
        click.echo(f"Chromium: {path}")
    else:
        click.echo("Installing Chromium...")
        result = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True, text=True)
        if result.returncode != 0:
            click.echo(f"Error: {result.stderr}", err=True)
            sys.exit(1)
        installed, path = _check_chromium()
        click.echo(f"Chromium: {path}")

    click.echo("Ready. Run: aitk browser start")


@group.command()
@click.option("--port", type=int, default=DEFAULT_PORT)
@click.option("--headed", is_flag=True, help="Show browser window")
@_run_async
async def start(port, headed):
    """Start browser with remote debugging."""
    chromium = _ensure_init()

    if _is_port_in_use(port):
        click.echo(f"Error: Port {port} in use", err=True)
        click.echo(f"Run: aitk browser close --port {port}", err=True)
        sys.exit(1)

    profile = Path.home() / f".cache/playwright-browser-{port}"
    profile.mkdir(parents=True, exist_ok=True)

    cmd = [
        chromium,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--window-size=1920,1080",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if not headed:
        cmd.extend(["--headless=new", "--disable-gpu", "--no-sandbox"])

    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

    # Wait for browser
    time.sleep(1)
    for _ in range(30):
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
                await browser.close()
                mode = "headed" if headed else "headless"
                click.echo(f"Started: port {port} ({mode})")
                return
        except Exception:
            time.sleep(0.5)

    click.echo("Error: Browser failed to start", err=True)
    sys.exit(1)


@group.command()
@click.argument("url")
@click.option("--port", type=int, default=DEFAULT_PORT)
@click.option("--new", is_flag=True, help="Open in new tab")
@_run_async
async def nav(url, port, new):
    """Navigate to URL."""
    try:
        pw, browser = await _connect(port)
        try:
            if new:
                page = await browser.contexts[0].new_page()
            else:
                page = await _get_page(browser)
            await page.goto(url, wait_until="domcontentloaded")
            click.echo(f"Navigated: {page.url}")
        finally:
            await browser.close()
            await pw.stop()
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo(f"Run: aitk browser start --port {port}", err=True)
        sys.exit(1)


@group.command()
@click.option("--path", type=click.Path(), help="Output path")
@click.option("--full", is_flag=True, help="Full page screenshot")
@click.option("--port", type=int, default=DEFAULT_PORT)
@_run_async
async def screenshot(path, full, port):
    """Take screenshot."""
    try:
        pw, browser = await _connect(port)
        try:
            page = await _get_page(browser)
            if path:
                filepath = Path(path)
            else:
                filepath = Path(tempfile.gettempdir()) / f"screenshot-{int(time.time())}.png"
            await page.screenshot(path=str(filepath), full_page=full)
            click.echo(f"Saved: {filepath}")
        finally:
            await browser.close()
            await pw.stop()
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command("click")
@click.argument("selector")
@click.option("--port", type=int, default=DEFAULT_PORT)
@_run_async
async def click_cmd(selector, port):
    """Click element."""
    try:
        pw, browser = await _connect(port)
        try:
            page = await _get_page(browser)
            await page.click(selector)
            click.echo(f"Clicked: {selector}")
        finally:
            await browser.close()
            await pw.stop()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command("type")
@click.argument("selector")
@click.argument("text")
@click.option("--port", type=int, default=DEFAULT_PORT)
@_run_async
async def type_cmd(selector, text, port):
    """Type text into input field."""
    try:
        pw, browser = await _connect(port)
        try:
            page = await _get_page(browser)
            await page.fill(selector, text)
            click.echo(f"Typed: {selector}")
        finally:
            await browser.close()
            await pw.stop()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.option("--port", type=int, default=DEFAULT_PORT)
@_run_async
async def a11y(port):
    """Get accessibility tree (useful for understanding page structure)."""
    try:
        pw, browser = await _connect(port)
        try:
            page = await _get_page(browser)
            snapshot = await page.accessibility.snapshot()
            click.echo(json.dumps(snapshot, indent=2))
        finally:
            await browser.close()
            await pw.stop()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.option("--port", type=int, default=DEFAULT_PORT)
@_run_async
async def status(port):
    """Check if browser is running."""
    try:
        pw, browser = await _connect(port)
        try:
            pages = browser.contexts[0].pages if browser.contexts else []
            click.echo(f"Running: port {port}, {len(pages)} tab(s)")
            if pages:
                click.echo(f"URL: {pages[-1].url}")
        finally:
            await browser.close()
            await pw.stop()
    except Exception:
        click.echo(f"Not running on port {port}")


@group.command()
@click.option("--port", type=int, default=DEFAULT_PORT)
@_run_async
async def close(port):
    """Close browser."""
    try:
        pw, browser = await _connect(port)
        await browser.close()
        await pw.stop()
    except Exception:
        pass

    if _kill_port(port):
        click.echo(f"Closed: port {port}")
    else:
        click.echo(f"Not running on port {port}")
