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
    """Parse KEY=value from env file."""
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'") or None
    except OSError:
        pass
    return None


def _walk_up_env(key: str) -> str | None:
    """Search parent directories for .env file containing key."""
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
