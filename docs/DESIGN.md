# AI Toolkit (`aitk`) - Implementation Guidelines

## Overview

Unified CLI for AI-powered tools. Install via `uv tool install`, discover via `--help`.

**Binary:** `aitk`
**Install:** `uv tool install git+https://github.com/Mandalorian007/aitk`

---

## Design Principles

### 1. Clear, Then Minimal

Clarity first. Then remove what doesn't help.

Tokens matter over time—every character is context an agent must process. But terse isn't the goal; *clear and concise* is.

```python
# Bad - verbose fluff
click.echo("Successfully generated image!")
click.echo(f"The file has been saved to: {filepath}")
click.echo("You can now use this image in your project.")

# Bad - too terse, unclear
click.echo(filepath)

# Good - clear and concise
click.echo(f"Saved: {filepath}")
```

Ask: "Would an agent or user know what just happened?"

### 2. Progressive Disclosure

Don't dump everything upfront. Let users drill down.

```
aitk --help              → tool list
aitk image --help        → subcommands
aitk image generate -h   → all options
```

### 3. Errors Are Actionable

When something fails, say what to do about it.

```
# Bad
Error: Authentication failed

# Good
Error: OPENAI_API_KEY not configured
  Run: aitk config
```

---

## Tools & Requirements

| Command | Purpose | Credential |
|---------|---------|------------|
| `aitk image` | Image generation | `OPENAI_API_KEY` |
| `aitk video` | Video generation | `OPENAI_API_KEY` |
| `aitk search` | Web search | `PERPLEXITY_API_KEY` |
| `aitk scrape` | Web scraping | `FIRECRAWL_API_KEY` |
| `aitk browser` | Browser automation | *None* |
| `aitk config` | Configure credentials | *None* |

---

## Credential Chain

Order of precedence:

```
1. Environment variable     → CI/CD, op run
2. ~/.config/aitk/config    → User defaults
3. Walk-up .env             → Project context
```

### Implementation (`env.py`)

```python
"""Credential chain and requirement decorator."""

from functools import wraps
from pathlib import Path
import os
import sys
import click


def get_credential(key: str) -> str | None:
    """Get credential: env → config → .env"""
    if val := os.environ.get(key):
        return val

    config = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "aitk/config"
    if config.exists() and (val := _parse_env(config, key)):
        return val

    return _walk_up_env(key)


def _parse_env(path: Path, key: str) -> str | None:
    try:
        for line in path.read_text().splitlines():
            if line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'") or None
    except OSError:
        pass
    return None


def _walk_up_env(key: str) -> str | None:
    current = Path.cwd()
    for _ in range(10):
        env = current / ".env"
        if env.exists():
            return _parse_env(env, key)
        if (p := current.parent) == current:
            break
        current = p
    return None


# Credential metadata for error messages
CREDENTIALS = {
    "OPENAI_API_KEY": "https://platform.openai.com/api-keys",
    "PERPLEXITY_API_KEY": "https://perplexity.ai/settings/api",
    "FIRECRAWL_API_KEY": "https://firecrawl.dev/app/api-keys",
}


def requires(*keys: str):
    """Decorator: fail fast if credentials missing."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            missing = [k for k in keys if not get_credential(k)]
            if missing:
                for k in missing:
                    click.echo(f"Missing: {k}", err=True)
                    if url := CREDENTIALS.get(k):
                        click.echo(f"  Get key: {url}", err=True)
                click.echo("Run: aitk config", err=True)
                sys.exit(1)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```

### Usage

```python
@image.command()
@requires("OPENAI_API_KEY")
def generate(prompt: str):
    client = OpenAI(api_key=get_credential("OPENAI_API_KEY"))
    ...
```

---

## Project Structure

```
aitk/
├── pyproject.toml
└── src/aitk/
    ├── __init__.py
    ├── env.py
    ├── image/commands.py
    ├── video/commands.py
    ├── search/commands.py
    ├── scrape/commands.py
    └── browser/commands.py
```

---

## pyproject.toml

```toml
[project]
name = "aitk"
version = "0.1.0"
description = "AI Toolkit CLI"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1.0",
    "httpx>=0.27.0",
    "openai>=1.0.0",
    "pillow>=10.0.0",
    "firecrawl-py>=1.0.0",
    "playwright>=1.40.0",
    "imageio[ffmpeg]>=2.34.0",
]

[project.scripts]
aitk = "aitk:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/aitk"]
```

---

## CLI Entry Point

```python
import click
from pathlib import Path
from . import image, video, search, scrape, browser

@click.group()
@click.version_option()
def cli():
    """
    AI Toolkit CLI.

    \b
    aitk image    Image generation
    aitk video    Video generation
    aitk search   Web search
    aitk scrape   Web scraping
    aitk browser  Browser automation
    aitk config   Configure credentials
    """
    pass

@cli.command()
def config():
    """Configure API keys."""
    config_dir = Path.home() / ".config/aitk"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config"

    keys = {}
    for key, tools in [
        ("OPENAI_API_KEY", "image, video"),
        ("PERPLEXITY_API_KEY", "search"),
        ("FIRECRAWL_API_KEY", "scrape"),
    ]:
        val = click.prompt(f"{key} ({tools})", default="", hide_input=True, show_default=False)
        if val:
            keys[key] = val

    with open(config_file, "w") as f:
        for k, v in keys.items():
            f.write(f"{k}={v}\n")
    config_file.chmod(0o600)
    click.echo(f"Saved: {config_file}")

cli.add_command(image.group, name="image")
cli.add_command(video.group, name="video")
cli.add_command(search.command, name="search")
cli.add_command(scrape.group, name="scrape")
cli.add_command(browser.group, name="browser")
```

---

## Migration Path

1. Scaffold structure
2. Implement `env.py`
3. Migrate image → video → search → scrape → browser
4. Test `aitk --help`
5. Push to GitHub
