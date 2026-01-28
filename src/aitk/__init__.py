"""AI Toolkit CLI."""

from pathlib import Path

import click

from .env import get_credential
from .env import cli as env_cli
from . import image, video, audio, search, scrape, browser, notion


@click.group()
@click.version_option()
def cli():
    """
    AI Toolkit CLI.

    \b
    aitk image    Image generation
    aitk video    Video generation
    aitk audio    Audio generation
    aitk search   Web search
    aitk scrape   Web scraping
    aitk browser  Browser automation
    aitk notion   Notion project boards
    aitk env      Manage encrypted .env files
    aitk config   Configure credentials
    """
    pass


@cli.command()
def config():
    """
    Interactive setup for API credentials.

    Prompts for each API key and saves to ~/.config/aitk/config.
    Press Enter to keep existing values. Keys are stored with 600 permissions.

    \b
    Keys prompted:
      OPENAI_API_KEY      Required for: image, video
      ELEVENLABS_API_KEY  Required for: audio
      PERPLEXITY_API_KEY  Required for: search
      FIRECRAWL_API_KEY   Required for: scrape

    \b
    Alternative: Set environment variables instead of using this command.
      export OPENAI_API_KEY=sk-...
      export ELEVENLABS_API_KEY=sk_...
      export PERPLEXITY_API_KEY=pplx-...
      export FIRECRAWL_API_KEY=fc-...

    \b
    Example:
      aitk config
    """
    config_dir = Path.home() / ".config/aitk"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config"

    keys = {}
    for key, tools in [
        ("OPENAI_API_KEY", "image, video"),
        ("ELEVENLABS_API_KEY", "audio"),
        ("PERPLEXITY_API_KEY", "search"),
        ("FIRECRAWL_API_KEY", "scrape"),
        ("NOTION_API_KEY", "notion"),
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
cli.add_command(audio.group, name="audio")
cli.add_command(search.command, name="search")
cli.add_command(scrape.group, name="scrape")
cli.add_command(browser.group, name="browser")
cli.add_command(notion.group, name="notion")
cli.add_command(env_cli.group, name="env")
