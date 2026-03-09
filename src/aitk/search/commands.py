"""Web search - Perplexity API."""

import sys

import click
import httpx

from ..env import requires, get_credential


@click.command()
@click.argument("query")
@click.pass_context
@requires("PERPLEXITY_API_KEY")
def command(ctx, query):
    """
    Search the web using Perplexity AI.

    Returns a summarized answer with source URLs. Good for current events,
    documentation lookups, and research questions.

    \b
    NOTE: Use single quotes for query arguments.

    \b
    Examples:
      aitk search 'latest python 3.13 features'
      aitk search 'how to configure nginx reverse proxy'
      aitk search 'OpenAI Sora API pricing'
    """
    api_key = get_credential("PERPLEXITY_API_KEY")

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": query}],
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        sources = data.get("search_results", []) or []

        click.echo(content)

        if sources:
            click.echo("\nSources:")
            for src in sources:
                click.echo(f"- {src.get('title', 'Untitled')}: {src.get('url', '')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: API returned {e.response.status_code}\n", err=True)
        click.echo(ctx.get_help())
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}\n", err=True)
        click.echo(ctx.get_help())
        sys.exit(1)
