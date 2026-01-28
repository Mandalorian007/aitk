"""Notion project board commands."""

import json
import sys

import click
import httpx

from ..env import requires, get_credential


NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _get_headers() -> dict:
    """Get headers for Notion API requests."""
    return {
        "Authorization": f"Bearer {get_credential('NOTION_API_KEY')}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _extract_title(page: dict) -> str:
    """Extract title from page properties."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            title_list = prop.get("title", [])
            if title_list:
                return "".join(t.get("plain_text", "") for t in title_list)
    return "Untitled"


def _extract_status(page: dict) -> str:
    """Extract status from page properties."""
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "status":
            status = prop.get("status")
            if status:
                return status.get("name", "")
    return ""


def _short_id(page_id: str) -> str:
    """Get last 8 chars of page ID (more unique than prefix)."""
    return page_id.replace("-", "")[-8:]


def _find_page(client: httpx.Client, db_id: str, identifier: str) -> dict | None:
    """Find page by full ID, short ID, or title substring."""
    response = client.post(
        f"{NOTION_API_URL}/databases/{db_id}/query",
        headers=_get_headers(),
        json={},
    )
    response.raise_for_status()
    pages = response.json().get("results", [])

    # Normalize identifier
    identifier_lower = identifier.lower()
    identifier_clean = identifier.replace("-", "")

    for page in pages:
        page_id = page.get("id", "")
        page_id_clean = page_id.replace("-", "")

        # Full ID match
        if page_id == identifier or page_id_clean == identifier_clean:
            return page

        # Short ID match (last 8 chars)
        if page_id_clean.endswith(identifier_clean):
            return page

        # Title substring match
        title = _extract_title(page).lower()
        if identifier_lower in title:
            return page

    return None


def _get_status_property_name(client: httpx.Client, db_id: str) -> str | None:
    """Get the name of the status property from database schema."""
    response = client.get(
        f"{NOTION_API_URL}/databases/{db_id}",
        headers=_get_headers(),
    )
    response.raise_for_status()
    props = response.json().get("properties", {})

    for name, prop in props.items():
        if prop.get("type") == "status":
            return name
    return None


def _get_title_property_name(client: httpx.Client, db_id: str) -> str | None:
    """Get the name of the title property from database schema."""
    response = client.get(
        f"{NOTION_API_URL}/databases/{db_id}",
        headers=_get_headers(),
    )
    response.raise_for_status()
    props = response.json().get("properties", {})

    for name, prop in props.items():
        if prop.get("type") == "title":
            return name
    return None


@click.group()
def group():
    """Notion project board commands."""
    pass


@group.command()
@requires("NOTION_API_KEY")
def dbs():
    """
    List accessible databases.

    Shows all databases the integration has access to.

    \b
    Example:
      aitk notion dbs
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{NOTION_API_URL}/search",
                headers=_get_headers(),
                json={"filter": {"property": "object", "value": "database"}},
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        if not results:
            click.echo("No databases found.")
            return

        for db in results:
            db_id = db.get("id", "")
            title_list = db.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_list) or "Untitled"
            click.echo(f"{db_id}  {title}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: API returned {e.response.status_code}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.option("--db", required=True, help="Database ID")
@click.option("-s", "--status", help="Filter by status")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@requires("NOTION_API_KEY")
def board(db, status, as_json):
    """
    List items in a database.

    \b
    Examples:
      aitk notion board --db abc123
      aitk notion board --db abc123 -s "In Progress"
      aitk notion board --db abc123 --json
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            body = {}
            if status:
                # Get status property name first
                status_prop = _get_status_property_name(client, db)
                if status_prop:
                    body["filter"] = {
                        "property": status_prop,
                        "status": {"equals": status},
                    }

            response = client.post(
                f"{NOTION_API_URL}/databases/{db}/query",
                headers=_get_headers(),
                json=body,
            )
            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])
        if not results:
            click.echo("No items found.")
            return

        if as_json:
            items = []
            for page in results:
                items.append({
                    "id": page.get("id", ""),
                    "short_id": _short_id(page.get("id", "")),
                    "status": _extract_status(page),
                    "title": _extract_title(page),
                    "url": page.get("url", ""),
                })
            click.echo(json.dumps(items, indent=2))
        else:
            for page in results:
                page_id = page.get("id", "")
                page_status = _extract_status(page)
                title = _extract_title(page)
                status_str = f"[{page_status}]" if page_status else ""
                click.echo(f"{page_id}  {status_str:15}  {title}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: API returned {e.response.status_code}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("identifier")
@click.option("--db", required=True, help="Database ID")
@requires("NOTION_API_KEY")
def view(identifier, db):
    """
    View item details.

    IDENTIFIER: page ID (full or suffix) or title substring.

    \b
    Examples:
      aitk notion view 2f603d27-83ff-8010-9d3b-eee56b8dd35b --db abc123
      aitk notion view 6b8dd35b --db abc123
      aitk notion view "My Task" --db abc123
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            page = _find_page(client, db, identifier)

        if not page:
            click.echo(f"No item found matching '{identifier}'", err=True)
            sys.exit(1)

        click.echo(f"ID:     {page.get('id', '')}")
        click.echo(f"Title:  {_extract_title(page)}")
        click.echo(f"Status: {_extract_status(page) or 'N/A'}")
        click.echo(f"URL:    {page.get('url', '')}")

        # Show other properties
        click.echo("\nProperties:")
        props = page.get("properties", {})
        for name, prop in props.items():
            prop_type = prop.get("type", "")
            if prop_type in ("title", "status"):
                continue  # Already shown above

            value = ""
            if prop_type == "rich_text":
                texts = prop.get("rich_text", [])
                value = "".join(t.get("plain_text", "") for t in texts)
            elif prop_type == "select":
                select = prop.get("select")
                value = select.get("name", "") if select else ""
            elif prop_type == "multi_select":
                selects = prop.get("multi_select", [])
                value = ", ".join(s.get("name", "") for s in selects)
            elif prop_type == "date":
                date = prop.get("date")
                if date:
                    value = date.get("start", "")
                    if date.get("end"):
                        value += f" → {date.get('end')}"
            elif prop_type == "checkbox":
                value = "Yes" if prop.get("checkbox") else "No"
            elif prop_type == "number":
                num = prop.get("number")
                value = str(num) if num is not None else ""
            elif prop_type == "url":
                value = prop.get("url", "") or ""
            elif prop_type == "email":
                value = prop.get("email", "") or ""
            elif prop_type == "phone_number":
                value = prop.get("phone_number", "") or ""
            elif prop_type == "people":
                people = prop.get("people", [])
                value = ", ".join(p.get("name", "") for p in people)

            if value:
                click.echo(f"  {name}: {value}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: API returned {e.response.status_code}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("title")
@click.option("--db", required=True, help="Database ID")
@click.option("-s", "--status", help="Initial status")
@requires("NOTION_API_KEY")
def add(title, db, status):
    """
    Create a new item.

    Creates a page in the database with the given title and optional status.

    \b
    Examples:
      aitk notion add "New task" --db abc123
      aitk notion add "Bug fix" --db abc123 -s "In Progress"
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            # Get property names from schema
            title_prop = _get_title_property_name(client, db)
            if not title_prop:
                click.echo("Error: Could not find title property in database", err=True)
                sys.exit(1)

            properties = {
                title_prop: {
                    "title": [{"text": {"content": title}}]
                }
            }

            if status:
                status_prop = _get_status_property_name(client, db)
                if status_prop:
                    properties[status_prop] = {"status": {"name": status}}

            response = client.post(
                f"{NOTION_API_URL}/pages",
                headers=_get_headers(),
                json={
                    "parent": {"database_id": db},
                    "properties": properties,
                },
            )
            response.raise_for_status()
            page = response.json()

        page_id = page.get("id", "")
        click.echo(f"Created: {page_id}  {title}")
        click.echo(f"URL: {page.get('url', '')}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: API returned {e.response.status_code}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("identifier")
@click.argument("status")
@click.option("--db", required=True, help="Database ID")
@requires("NOTION_API_KEY")
def move(identifier, status, db):
    """
    Change item status.

    IDENTIFIER: page ID (full or suffix) or title substring.

    \b
    Examples:
      aitk notion move 2f603d27-83ff-8010-9d3b-eee56b8dd35b Done --db abc123
      aitk notion move 6b8dd35b Done --db abc123
      aitk notion move "My Task" "In Progress" --db abc123
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            page = _find_page(client, db, identifier)
            if not page:
                click.echo(f"No item found matching '{identifier}'", err=True)
                sys.exit(1)

            page_id = page.get("id", "")
            status_prop = _get_status_property_name(client, db)
            if not status_prop:
                click.echo("Error: No status property found in database", err=True)
                sys.exit(1)

            response = client.patch(
                f"{NOTION_API_URL}/pages/{page_id}",
                headers=_get_headers(),
                json={
                    "properties": {
                        status_prop: {"status": {"name": status}}
                    }
                },
            )
            response.raise_for_status()

        click.echo(f"Moved: {page_id}  {_extract_title(page)} → {status}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: API returned {e.response.status_code}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("identifier")
@click.option("--db", required=True, help="Database ID")
@requires("NOTION_API_KEY")
def delete(identifier, db):
    """
    Delete (archive) an item.

    IDENTIFIER: page ID (full or suffix) or title substring.

    \b
    Examples:
      aitk notion delete 2f603d27-83ff-8010-9d3b-eee56b8dd35b --db abc123
      aitk notion delete 6b8dd35b --db abc123
      aitk notion delete "My Task" --db abc123
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            page = _find_page(client, db, identifier)
            if not page:
                click.echo(f"No item found matching '{identifier}'", err=True)
                sys.exit(1)

            page_id = page.get("id", "")
            title = _extract_title(page)

            response = client.patch(
                f"{NOTION_API_URL}/pages/{page_id}",
                headers=_get_headers(),
                json={"archived": True},
            )
            response.raise_for_status()

        click.echo(f"Deleted: {page_id}  {title}")

    except httpx.HTTPStatusError as e:
        click.echo(f"Error: API returned {e.response.status_code}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
