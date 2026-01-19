"""CLI commands for env store."""

import sys
from pathlib import Path

import click

from . import store


@click.group()
def group():
    """
    Manage age-encrypted .env files in a private GitHub repo.

    \b
    Commands:
      aitk env init          Generate age key pair
      aitk env push owner/repo   Encrypt and push .env files to store
      aitk env pull owner/repo   Decrypt and pull .env files from store
      aitk env diff owner/repo   Compare local vs store keys
      aitk env list [owner/repo] List repos or files in store

    \b
    Setup:
      1. Create a private GitHub repo for your env store
      2. Run: aitk env init
      3. Add ENV_STORE_REPO=owner/repo to ~/.config/aitk/config

    \b
    Config (~/.config/aitk/config):
      ENV_STORE_KEY=AGE-SECRET-KEY-...   # Private key (decrypt)
      ENV_STORE_PUBLIC_KEY=age1...       # Public key (encrypt)
      ENV_STORE_REPO=owner/env-store     # GitHub repo
    """
    pass


@group.command()
def init():
    """
    Generate age key pair for encryption.

    Creates a new age key pair and displays config lines to add
    to ~/.config/aitk/config. Refuses to run if keys already exist.

    \b
    Requires: age CLI (brew install age)

    \b
    Example:
      aitk env init
    """
    try:
        secret_key, public_key = store.init()

        click.echo("Generated age key pair.\n")
        click.echo("Add these lines to ~/.config/aitk/config:\n")
        click.echo(f"ENV_STORE_KEY={secret_key}")
        click.echo(f"ENV_STORE_PUBLIC_KEY={public_key}")
        click.echo("\nAlso add your env store repo:")
        click.echo("ENV_STORE_REPO=owner/env-store")

    except store.EnvStoreError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("repo")
def push(repo):
    """
    Encrypt and push .env files to store.

    Reads all .env files in the current directory (excluding .env.example,
    .env.sample, .env.template), strips comments, encrypts with age,
    and commits to your env store repo.

    \b
    REPO: owner/repo format (e.g., myorg/myapp)

    \b
    Examples:
      aitk env push myorg/myapp
      aitk env push personal/side-project
    """
    try:
        pushed = store.push(repo)
        for f in pushed:
            click.echo(f"Pushed: {f}")
        click.echo(f"\nStored {len(pushed)} file(s) to {repo}")

    except store.EnvStoreError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("repo")
def pull(repo):
    """
    Decrypt and pull .env files from store.

    Fetches encrypted .env files from your env store repo, decrypts
    them with your age key, and writes to the current directory
    with 0600 permissions.

    \b
    REPO: owner/repo format (e.g., myorg/myapp)

    \b
    Examples:
      aitk env pull myorg/myapp
      aitk env pull personal/side-project
    """
    try:
        created = store.pull(repo)
        for f in created:
            click.echo(f"Created: {f}")
        click.echo(f"\nPulled {len(created)} file(s) from {repo}")

    except store.EnvStoreError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("repo")
@click.option("--reveal", is_flag=True, help="Show actual values instead of masked")
def diff(repo, reveal):
    """
    Compare local .env keys with store.

    Shows which keys exist only locally, only in store, or in both.
    Values are masked by default; use --reveal to show actual values.

    \b
    REPO: owner/repo format (e.g., myorg/myapp)

    \b
    Examples:
      aitk env diff myorg/myapp
      aitk env diff myorg/myapp --reveal
    """
    try:
        result = store.diff(repo, reveal=reveal)

        if result["local_only"]:
            click.echo("Local only:")
            for k, v in result["local_only"].items():
                click.echo(f"  {k}={v}")

        if result["store_only"]:
            click.echo("Store only:")
            for k, v in result["store_only"].items():
                click.echo(f"  {k}={v}")

        if result["both"]:
            click.echo("Both:")
            for k, v in result["both"].items():
                click.echo(f"  {k}={v}")

        if not any(result.values()):
            click.echo("No .env keys found")

    except store.EnvStoreError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command("list")
@click.argument("repo", required=False)
def list_cmd(repo):
    """
    List repos or files in env store.

    Without arguments, lists all repos in the store.
    With a repo argument, lists .env files for that repo.

    \b
    Examples:
      aitk env list              # List all repos
      aitk env list myorg/myapp  # List files for repo
    """
    try:
        if repo:
            files = store.list_files(repo)
            if files:
                for f in files:
                    click.echo(f)
            else:
                click.echo(f"No .env files found for {repo}")
        else:
            repos = store.list_repos()
            if repos:
                for r in repos:
                    click.echo(r)
            else:
                click.echo("No repos in env store")

    except store.EnvStoreError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
