"""Web scraping - Firecrawl."""

import sys

import click
from firecrawl import Firecrawl

from ..env import requires, get_credential


def _get_client() -> Firecrawl:
    return Firecrawl(api_key=get_credential("FIRECRAWL_API_KEY"))


@click.group()
def group():
    """Web scraping with Firecrawl."""
    pass


@group.command()
@click.argument("url")
@click.option("--only-main", is_flag=True, help="Extract only main content")
@requires("FIRECRAWL_API_KEY")
def page(url, only_main):
    """Scrape URL and return markdown."""
    client = _get_client()

    try:
        result = client.scrape(
            url,
            formats=["markdown"],
            only_main_content=only_main if only_main else None,
        )

        if hasattr(result, "markdown"):
            markdown = result.markdown
        elif isinstance(result, dict):
            markdown = result.get("markdown", "")
        else:
            markdown = str(result)

        if markdown:
            click.echo(markdown)
        else:
            click.echo("Error: No content extracted", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("url")
@click.option("-s", "--search", help="Filter URLs by search term")
@click.option("-l", "--limit", default=100, help="Max URLs to return")
@requires("FIRECRAWL_API_KEY")
def map(url, search, limit):
    """Discover all URLs on a website."""
    client = _get_client()

    try:
        options = {"limit": limit}
        if search:
            options["search"] = search

        result = client.map(url, **options)

        if hasattr(result, "links"):
            links = result.links
        elif isinstance(result, dict):
            links = result.get("links", [])
        elif isinstance(result, list):
            links = result
        else:
            links = []

        if not links:
            click.echo("No URLs found", err=True)
            sys.exit(1)

        for link in links:
            if isinstance(link, dict):
                click.echo(link.get("url", link))
            elif hasattr(link, "url"):
                click.echo(link.url)
            else:
                click.echo(str(link))

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
