"""OCR using macOS Vision framework (lazy-loaded)."""

from pathlib import Path

from .errors import require_macos, GuiError

require_macos()


class OCRNotAvailableError(GuiError):
    """Vision framework not available."""

    pass


def ocr_image(path: str | Path) -> list[dict]:
    """Extract text from an image using Vision framework.

    Args:
        path: Path to image file (PNG, JPEG, etc.)

    Returns:
        List of dicts with text, confidence, x, y, width, height keys.
        Coordinates are in pixels from top-left of image.

    Raises:
        OCRNotAvailableError: If Vision framework not installed.
        FileNotFoundError: If image file doesn't exist.
    """
    try:
        import Vision
        from Quartz import (
            CGImageSourceCreateWithURL,
            CGImageSourceCreateImageAtIndex,
        )
        from Foundation import NSURL
    except ImportError:
        raise OCRNotAvailableError(
            "Vision framework not available.\n"
            "Install: uv pip install 'aitk[ocr]'"
        )

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    # Load image
    url = NSURL.fileURLWithPath_(str(path.absolute()))
    image_source = CGImageSourceCreateWithURL(url, None)
    if not image_source:
        raise GuiError(f"Could not load image: {path}")

    cg_image = CGImageSourceCreateImageAtIndex(image_source, 0, None)
    if not cg_image:
        raise GuiError(f"Could not create image from: {path}")

    # Get image dimensions for coordinate conversion
    from Quartz import CGImageGetWidth, CGImageGetHeight

    img_width = CGImageGetWidth(cg_image)
    img_height = CGImageGetHeight(cg_image)

    # Create request handler and text recognition request
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    # Perform OCR
    success, error = handler.performRequests_error_([request], None)
    if not success:
        raise GuiError(f"OCR failed: {error}")

    results = []
    observations = request.results() or []

    for obs in observations:
        # Get top candidate
        candidates = obs.topCandidates_(1)
        if not candidates:
            continue

        candidate = candidates[0]
        text = candidate.string()
        confidence = candidate.confidence()

        # Get bounding box (normalized 0-1, origin bottom-left)
        bbox = obs.boundingBox()

        # Convert to pixel coordinates (origin top-left)
        x = int(bbox.origin.x * img_width)
        y = int((1 - bbox.origin.y - bbox.size.height) * img_height)
        width = int(bbox.size.width * img_width)
        height = int(bbox.size.height * img_height)

        results.append({
            "text": text,
            "confidence": round(confidence, 3),
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        })

    return results


def ocr_screen(display_index: int | None = None) -> list[dict]:
    """Capture screen and perform OCR.

    Args:
        display_index: Which display to capture (0-indexed). None for all.

    Returns:
        List of text regions with coordinates.
    """
    import tempfile
    from . import screen

    # Capture to temp file
    temp_path = Path(tempfile.gettempdir()) / f"aitk-ocr-{id(object())}.png"
    try:
        screen.capture_screen(temp_path, display_index=display_index)
        return ocr_image(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
