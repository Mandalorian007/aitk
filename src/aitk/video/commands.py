"""Video generation - OpenAI Sora."""

import io
import sys
import time
from pathlib import Path

import click
from openai import OpenAI
from PIL import Image

from ..env import requires, get_credential


def _get_client() -> OpenAI:
    return OpenAI(api_key=get_credential("OPENAI_API_KEY"))


def _prepare_image(image_path: Path, target_size: str) -> io.BytesIO:
    """Resize/pad image to match video dimensions."""
    width, height = map(int, target_size.split("x"))

    with Image.open(image_path) as img:
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")

        scale = min(width / img.width, height / img.height)
        new_w, new_h = int(img.width * scale), int(img.height * scale)
        resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (width, height), (0, 0, 0))
        x, y = (width - new_w) // 2, (height - new_h) // 2

        if resized.mode == "RGBA":
            canvas.paste(resized, (x, y), resized)
        else:
            canvas.paste(resized, (x, y))

        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        buffer.seek(0)
        buffer.name = "image.png"
        return buffer


def _poll(client: OpenAI, video_id: str) -> object:
    """Poll until video completes."""
    while True:
        video = client.videos.retrieve(video_id)
        progress = getattr(video, "progress", 0)
        sys.stdout.write(f"\rProgress: {progress}%")
        sys.stdout.flush()

        if video.status == "completed":
            sys.stdout.write("\n")
            return video
        elif video.status == "failed":
            sys.stdout.write("\n")
            error = getattr(getattr(video, "error", None), "message", "Unknown error")
            raise Exception(f"Generation failed: {error}")

        time.sleep(5)


@click.group()
def group():
    """Video generation with OpenAI Sora."""
    pass


@group.command()
@click.argument("image", type=click.Path(exists=True))
@click.argument("prompt")
@click.option("-o", "--output", help="Output path")
@click.option("-s", "--seconds", type=click.Choice(["4", "8", "12"]), default="4")
@click.option("--size", type=click.Choice(["1280x720", "720x1280", "1792x1024", "1024x1792"]), default="1280x720")
@click.option("--no-wait", is_flag=True, help="Return job ID without waiting")
@requires("OPENAI_API_KEY")
def create(image, prompt, output, seconds, size, no_wait):
    """Create video from image. Image becomes first frame."""
    client = _get_client()
    image_path = Path(image)

    try:
        prepared = _prepare_image(image_path, size)

        video = client.videos.create(
            model="sora-2",
            prompt=prompt,
            input_reference=prepared,
            seconds=seconds,
            size=size,
        )

        if no_wait:
            click.echo(video.id)
            return

        video = _poll(client, video.id)

        output_path = Path(output) if output else image_path.with_suffix(".mp4")
        if output and not Path(output).suffix:
            output_path = Path(f"{output}.mp4")

        content = client.videos.download_content(video.id, variant="video")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content.write_to_file(str(output_path))

        click.echo(f"Saved: {output_path}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("video_id")
@requires("OPENAI_API_KEY")
def status(video_id):
    """Check video generation status."""
    client = _get_client()

    try:
        video = client.videos.retrieve(video_id)
        click.echo(f"ID: {video.id}")
        click.echo(f"Status: {video.status}")
        click.echo(f"Progress: {getattr(video, 'progress', 0)}%")

        if video.status == "failed":
            error = getattr(video, "error", None)
            if error:
                click.echo(f"Error: {getattr(error, 'message', 'Unknown')}", err=True)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("video_id")
@click.option("-o", "--output", default="video.mp4")
@requires("OPENAI_API_KEY")
def download(video_id, output):
    """Download completed video."""
    client = _get_client()

    try:
        video = client.videos.retrieve(video_id)
        if video.status != "completed":
            click.echo(f"Error: Video not ready (status: {video.status})", err=True)
            sys.exit(1)

        output_path = Path(output)
        content = client.videos.download_content(video_id, variant="video")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content.write_to_file(str(output_path))

        click.echo(f"Saved: {output_path}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command("list")
@click.option("-n", "--limit", default=10)
@requires("OPENAI_API_KEY")
def list_videos(limit):
    """List recent video jobs."""
    client = _get_client()

    try:
        result = client.videos.list(limit=limit)
        if not result.data:
            click.echo("No videos found")
            return

        for video in result.data:
            icon = {"completed": "+", "failed": "x", "in_progress": "~", "queued": "."}.get(video.status, "?")
            progress = f" ({getattr(video, 'progress', 0)}%)" if video.status in ("queued", "in_progress") else ""
            click.echo(f"[{icon}] {video.id} {video.status}{progress}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@group.command()
@click.argument("input_video", type=click.Path(exists=True))
@click.option("-o", "--output", help="Output path")
@click.option("--fps", type=int, default=15)
@click.option("--width", type=int, default=None)
@click.option("--quality", type=int, default=80)
def webpify(input_video, output, fps, width, quality):
    """Convert MP4 to animated WebP."""
    import imageio.v3 as iio

    input_path = Path(input_video)
    output_path = Path(output) if output else input_path.with_suffix(".webp")

    try:
        frames = iio.imread(input_path, plugin="pyav")
        orig_h, orig_w = frames[0].shape[:2]

        # Sample frames for target FPS
        frame_step = max(1, round(24 / fps))
        frames = frames[::frame_step]

        pil_frames = []
        for frame in frames:
            img = Image.fromarray(frame)
            if width and width != orig_w:
                scale = width / orig_w
                img = img.resize((width, int(orig_h * scale)), Image.Resampling.LANCZOS)
            pil_frames.append(img)

        duration = int(1000 / fps)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pil_frames[0].save(
            output_path,
            save_all=True,
            append_images=pil_frames[1:],
            duration=duration,
            loop=0,
            quality=quality,
        )

        kb = output_path.stat().st_size / 1024
        w, h = pil_frames[0].size
        click.echo(f"Saved: {output_path} ({len(pil_frames)} frames, {w}x{h}, {kb:.1f}KB)")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
