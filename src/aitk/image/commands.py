"""Image generation - OpenAI GPT Image."""

import base64
import io
import sys
from datetime import datetime
from pathlib import Path

import click
from openai import OpenAI

from ..env import requires, get_credential


def _get_client() -> OpenAI:
    return OpenAI(api_key=get_credential("OPENAI_API_KEY"))


def _generate_filename(fmt: str) -> str:
    return f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}"


@click.group()
def group():
    """Image generation with OpenAI GPT Image."""
    pass


@group.command()
@click.argument("prompt")
@click.option("-o", "--output", help="Output path")
@click.option("-r", "--reference", multiple=True, type=click.Path(exists=True), help="Reference image(s)")
@click.option("-s", "--size", type=click.Choice(["1024x1024", "1536x1024", "1024x1536"]), default="1024x1024")
@click.option("-q", "--quality", type=click.Choice(["low", "medium", "high"]), default=None)
@click.option("-f", "--format", "output_format", type=click.Choice(["png", "jpeg", "webp"]), default="png")
@click.option("-b", "--background", type=click.Choice(["opaque", "transparent"]), default=None)
@click.option("-n", "--count", type=click.IntRange(1, 10), default=1)
@requires("OPENAI_API_KEY")
def generate(prompt, output, reference, size, quality, output_format, background, count):
    """Generate image from text prompt."""
    client = _get_client()
    handles = []

    try:
        if reference:
            handles = [open(img, "rb") for img in reference]
            params = {
                "model": "gpt-image-1",
                "image": handles if len(handles) > 1 else handles[0],
                "prompt": prompt,
                "n": count,
                "size": size,
            }
            if quality:
                params["quality"] = quality
            if background:
                params["background"] = background
            if output_format != "png":
                params["output_format"] = output_format
            result = client.images.edit(**params)
        else:
            params = {
                "model": "gpt-image-1",
                "prompt": prompt,
                "n": count,
                "size": size,
            }
            if quality:
                params["quality"] = quality
            if background:
                params["background"] = background
            if output_format != "png":
                params["output_format"] = output_format
            result = client.images.generate(**params)

        for i, img_data in enumerate(result.data):
            if output:
                if count > 1:
                    base, ext = Path(output).stem, Path(output).suffix or f".{output_format}"
                    filepath = f"{base}_{i+1}{ext}"
                else:
                    filepath = output if Path(output).suffix else f"{output}.{output_format}"
            else:
                if count > 1:
                    filepath = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i+1}.{output_format}"
                else:
                    filepath = _generate_filename(output_format)

            image_bytes = base64.b64decode(img_data.b64_json)
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_bytes(image_bytes)
            click.echo(f"Saved: {filepath}")

    except Exception as e:
        msg = str(e).lower()
        if "rate_limit" in msg:
            click.echo("Error: Rate limit exceeded", err=True)
        elif "content_policy" in msg:
            click.echo("Error: Content policy violation", err=True)
        else:
            click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        for h in handles:
            h.close()


@group.command()
@click.option("-i", "--image", "images", multiple=True, required=True, type=click.Path(exists=True))
@click.argument("prompt")
@click.option("-o", "--output", help="Output path")
@click.option("-s", "--size", type=click.Choice(["1024x1024", "1536x1024", "1024x1536"]), default=None)
@click.option("-q", "--quality", type=click.Choice(["low", "medium", "high"]), default=None)
@click.option("-f", "--format", "output_format", type=click.Choice(["png", "jpeg", "webp"]), default="png")
@click.option("-b", "--background", type=click.Choice(["opaque", "transparent"]), default=None)
@requires("OPENAI_API_KEY")
def edit(images, prompt, output, size, quality, output_format, background):
    """Edit image(s) with text prompt."""
    client = _get_client()
    handles = []

    try:
        handles = [open(p, "rb") for p in images]
        params = {
            "model": "gpt-image-1",
            "image": handles if len(handles) > 1 else handles[0],
            "prompt": prompt,
        }
        if size:
            params["size"] = size
        if quality:
            params["quality"] = quality
        if background:
            params["background"] = background
        if output_format != "png":
            params["output_format"] = output_format

        result = client.images.edit(**params)

        output_path = Path(output) if output else Path(images[0])
        if output and not Path(output).suffix:
            output_path = Path(f"{output}.{output_format}")

        image_bytes = base64.b64decode(result.data[0].b64_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)
        click.echo(f"Saved: {output_path}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    finally:
        for h in handles:
            h.close()


@group.command()
@click.argument("input_image", type=click.Path(exists=True))
@click.option("-o", "--output", help="Output path")
@click.option("-s", "--size", type=int, default=128, help="Size in pixels (default: 128)")
@click.option("--max-kb", type=int, default=256, help="Max file size in KB (default: 256)")
def emojify(input_image, output, size, max_kb):
    """Convert image to Discord emoji format (128x128, <256KB)."""
    from PIL import Image

    input_path = Path(input_image)
    output_path = Path(output) if output else input_path.with_stem(input_path.stem.replace("_", "-"))

    try:
        with Image.open(input_path) as img:
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            resized = img.resize((size, size), Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            fmt = output_path.suffix.upper().lstrip(".") or "PNG"
            if fmt == "JPG":
                fmt = "JPEG"

            resized.save(buffer, format=fmt, optimize=True)

            # Reduce quality if too large
            max_bytes = max_kb * 1024
            quality = 90
            while buffer.tell() > max_bytes and quality > 20:
                buffer = io.BytesIO()
                resized.save(buffer, format=fmt, optimize=True, quality=quality)
                quality -= 10

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(buffer.getvalue())

            kb = buffer.tell() / 1024
            click.echo(f"Saved: {output_path} ({size}x{size}, {kb:.1f}KB)")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
