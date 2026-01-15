"""AI Toolkit CLI."""

from pathlib import Path

import click

from .env import get_credential
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
        existing = get_credential(key)
        prompt_text = f"{key} ({tools})"
        if existing:
            prompt_text += " [configured]"
        val = click.prompt(prompt_text, default="", hide_input=True, show_default=False)
        if val:
            keys[key] = val
        elif existing:
            keys[key] = existing

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
