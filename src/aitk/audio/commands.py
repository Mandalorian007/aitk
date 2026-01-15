"""Audio generation - ElevenLabs text-to-speech."""

import sys
from pathlib import Path

import click
import httpx

from ..env import requires, get_credential


API_BASE = "https://api.elevenlabs.io/v1"


def _get_headers() -> dict:
    return {"xi-api-key": get_credential("ELEVENLABS_API_KEY")}


@click.group()
def group():
    """Audio generation with ElevenLabs."""
    pass


@group.command()
@click.argument("text")
@click.option("-o", "--output", default="speech.mp3", help="Output path (default: speech.mp3)")
@click.option("-v", "--voice", default="Rachel", help="Voice name or ID (default: Rachel)")
@click.option("--model", default="eleven_multilingual_v2", help="Model ID (default: eleven_multilingual_v2)")
@click.option("--stability", type=float, default=0.5, help="Voice stability 0-1 (default: 0.5)")
@click.option("--similarity", type=float, default=0.75, help="Clarity + similarity 0-1 (default: 0.75)")
@click.option("--style", type=float, default=0.0, help="Style exaggeration 0-1 (default: 0)")
@requires("ELEVENLABS_API_KEY")
def speak(text, output, voice, model, stability, similarity, style):
    """
    Convert text to speech.

    Uses ElevenLabs API to generate natural-sounding speech from text.
    Run 'aitk audio voices' to see available voices.

    \b
    Examples:
      aitk audio speak "Hello, world!"
      aitk audio speak "Welcome to the demo" -o welcome.mp3
      aitk audio speak "Exciting news!" -v Josh --style 0.5
      aitk audio speak "Bonjour le monde" -v Antoni --model eleven_multilingual_v2
    """
    try:
        voice_id = _resolve_voice(voice)

        response = httpx.post(
            f"{API_BASE}/text-to-speech/{voice_id}",
            headers=_get_headers(),
            json={
                "text": text,
                "model_id": model,
                "voice_settings": {
                    "stability": stability,
                    "similarity_boost": similarity,
                    "style": style,
                },
            },
            timeout=60.0,
        )
        response.raise_for_status()

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        kb = output_path.stat().st_size / 1024
        click.echo(f"Saved: {output_path} ({kb:.1f}KB)")

    except httpx.HTTPStatusError as e:
        _handle_error(e)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@requires("ELEVENLABS_API_KEY")
def voices():
    """
    List available voices.

    Shows voice name, ID, and category for each available voice.
    Use the name or ID with the -v/--voice option in 'aitk audio speak'.

    \b
    Example:
      aitk audio voices
    """
    try:
        response = httpx.get(
            f"{API_BASE}/voices",
            headers=_get_headers(),
            timeout=30.0,
        )
        response.raise_for_status()

        data = response.json()
        voices_list = data.get("voices", [])

        if not voices_list:
            click.echo("No voices found")
            return

        for v in voices_list:
            name = v.get("name", "Unknown")
            vid = v.get("voice_id", "")
            category = v.get("category", "")
            labels = v.get("labels", {})
            accent = labels.get("accent", "")
            gender = labels.get("gender", "")

            info = f"{name} ({vid[:8]}...)"
            if category:
                info += f" [{category}]"
            if gender or accent:
                details = ", ".join(filter(None, [gender, accent]))
                info += f" - {details}"

            click.echo(info)

    except httpx.HTTPStatusError as e:
        _handle_error(e)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# Default voice IDs for common voices (fallback when voices_read permission unavailable)
DEFAULT_VOICES = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    "drew": "29vD33N1CtxCmqQRPOHJ",
    "clyde": "2EiwWnXFnvU5JabPnv8n",
    "paul": "5Q0t7uMcjvnagumLfvZi",
    "domi": "AZnzlk1XvdvUeBnXmlld",
    "dave": "CYw3kZ02Hs0563khs1Fj",
    "fin": "D38z5RcWu1voky8WS1ja",
    "sarah": "EXAVITQu4vr4xnSDxMaL",
    "antoni": "ErXwobaYiN019PkySvjV",
    "thomas": "GBv7mTt0atIp3Br8iCZE",
    "charlie": "IKne3meq5aSn9XLyUdCD",
    "george": "JBFqnCBsd6RMkjVDRZzb",
    "emily": "LcfcDJNUP1GQjkzn1xUU",
    "elli": "MF3mGyEYCl7XYWbV9V6O",
    "callum": "N2lVS1w4EtoT3dr4eOWO",
    "patrick": "ODq5zmih8GrVes37Dizd",
    "harry": "SOYHLrjzK2X1ezoPC6cr",
    "liam": "TX3LPaxmHKxFdv7VOQHJ",
    "dorothy": "ThT5KcBeYPX3keUQqHPh",
    "josh": "TxGEqnHWrfWFTfGW9XjX",
    "arnold": "VR6AewLTigWG4xSOukaG",
    "charlotte": "XB0fDUnXU5powFXDhCwa",
    "alice": "Xb7hH8MSUJpSbSDYk0k2",
    "matilda": "XrExE9yKIg1WjnnlVkGX",
    "james": "ZQe5CZNOzWyzPSCn5a3c",
    "joseph": "Zlb1dXrM653N07WRdFW3",
    "jessica": "cgSgspJ2msm6clMCkdW9",
    "michael": "flq6f7yk4E4fJM5XTYuZ",
    "ethan": "g5CIjZEefAph4nQFvHAz",
    "chris": "iP95p4xoKVk53GoZ742B",
    "gigi": "jBpfuIE2acCO8z3wKNLl",
    "freya": "jsCqWAovK2LkecY7zXl4",
    "brian": "nPczCjzI2devNBz1zQrb",
    "grace": "oWAxZDx7w5VEj9dCyTzz",
    "daniel": "onwK4e9ZLuTAKqWW03F9",
    "lily": "pFZP5JQG7iQjIQuC4Bku",
    "serena": "pMsXgVXv3BLzUgSXRplE",
    "adam": "pNInz6obpgDQGcFmaJgB",
    "nicole": "piTKgcLEGmPE4e6mEKli",
    "bill": "pqHfZKP75CvOlQylNhV4",
    "jessie": "t0jbNlBVZ17f02VDIeMI",
    "sam": "yoZ06aMxZJJ28mfd3POQ",
    "glinda": "z9fAnlkpzviPz146aGWa",
}


def _resolve_voice(voice: str) -> str:
    """Resolve voice name to ID, or return as-is if already an ID."""
    if len(voice) > 15 and voice.isalnum():
        return voice

    # Check default voices first
    if voice.lower() in DEFAULT_VOICES:
        return DEFAULT_VOICES[voice.lower()]

    try:
        response = httpx.get(
            f"{API_BASE}/voices",
            headers=_get_headers(),
            timeout=30.0,
        )
        response.raise_for_status()

        for v in response.json().get("voices", []):
            if v.get("name", "").lower() == voice.lower():
                return v["voice_id"]
            if v.get("voice_id") == voice:
                return voice

        raise click.ClickException(f"Voice not found: {voice}\nRun 'aitk audio voices' to see available voices.")

    except httpx.HTTPStatusError as e:
        # If missing voices_read permission, suggest using a known voice
        try:
            detail = e.response.json().get("detail", {})
            if isinstance(detail, dict) and detail.get("status") == "missing_permissions":
                raise click.ClickException(
                    f"Voice '{voice}' not in defaults and API lacks voices_read permission.\n"
                    f"Use a default voice: {', '.join(list(DEFAULT_VOICES.keys())[:5])}..."
                )
        except click.ClickException:
            raise
        except Exception:
            pass
        _handle_error(e)


def _handle_error(e: httpx.HTTPStatusError):
    """Handle HTTP errors with user-friendly messages."""
    try:
        detail = e.response.json().get("detail", {})
        if isinstance(detail, dict):
            status = detail.get("status", "")
            msg = detail.get("message", str(e))
            if status == "missing_permissions":
                click.echo(f"Error: {msg}", err=True)
                click.echo("Check API key permissions at https://elevenlabs.io/app/settings/api-keys", err=True)
                sys.exit(1)
        else:
            msg = detail or str(e)
    except Exception:
        msg = str(e)

    if e.response.status_code == 401:
        click.echo("Error: Invalid API key", err=True)
    elif e.response.status_code == 429:
        click.echo("Error: Rate limit exceeded", err=True)
    else:
        click.echo(f"Error: {msg}", err=True)
    sys.exit(1)
