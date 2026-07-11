import contextlib
import http
import logging
import os
import time
import uuid

import requests
from flask import current_app
from PIL import Image

from app.errors import ImageFetchError

_logger = logging.getLogger(__name__)

# Rungs span the real render sizes: ~200px (smallest desktop grid cell at 1x)
# up to ~1200px (a near-full-width mobile poster on a 3x-DPR phone). Spaced at
# roughly 1.5x so no device over-fetches by much. 500 is retained so the
# existing warm w500/ cache stays valid. Widening this only adds storage plus a
# one-time resize per new width; browsers still download a single source each.
POSTER_WIDTHS = (200, 300, 500, 780, 1200)

# Width used for the plain `src` fallback when a browser ignores `srcset`.
# Must be a member of POSTER_WIDTHS.
POSTER_SRC_WIDTH = 500

# JPEG encode quality for resized posters. PIL defaults to 75, which softens
# poster detail; 85 is the usual quality/size sweet spot.
POSTER_JPEG_QUALITY = 85


def get_image_base_path() -> str:
    path = current_app.config.get("POSTER_DIR")
    if path is None:
        raise ValueError("POSTER_DIR not configured")
    os.makedirs(path, exist_ok=True)
    return path


def get_tmdb_image_base_url() -> str:
    url = current_app.config.get("TMDB_IMAGE_BASE_URL")
    if url is None:
        raise ValueError("TMDB_IMAGE_BASE_URL not configured")
    return url.rstrip("/")


def get_tmdb_image_url(remote_filename: str) -> str:
    return f"{get_tmdb_image_base_url()}/{remote_filename}"


def fetch_image(remote_filename: str, size: str = "original") -> None:
    target_filename = f"{get_image_base_path()}/{size}/{remote_filename}"
    remote_url = get_tmdb_image_url(remote_filename)
    response = requests.get(remote_url, timeout=10)
    if response.status_code != http.HTTPStatus.OK:
        raise ImageFetchError(f"Failed to fetch image from {remote_url}")
    os.makedirs(os.path.dirname(target_filename), exist_ok=True)
    # Atomic write so concurrent fetchers can't see a partial file or fail
    # on a write collision. Identical content from TMDB makes replace idempotent.
    tmp_filename = f"{target_filename}.{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp_filename, "wb") as file:
            file.write(response.content)
        os.replace(tmp_filename, target_filename)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.remove(tmp_filename)
        raise


def resize_image(original_file: str, width: int, target_filename: str) -> None:
    image = Image.open(original_file)
    # LANCZOS downscales noticeably sharper than PIL's default (BICUBIC).
    image.thumbnail((width, width * 3), resample=Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(target_filename), exist_ok=True)
    # Keep the original extension on the tmp file so PIL infers the format.
    ext = os.path.splitext(target_filename)[1]
    tmp_filename = f"{target_filename}.{uuid.uuid4().hex}.tmp{ext}"
    try:
        # quality only affects JPEG output; PIL ignores it for other formats.
        image.save(tmp_filename, quality=POSTER_JPEG_QUALITY)
        os.replace(tmp_filename, target_filename)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.remove(tmp_filename)
        raise


def ensure_image_exists(filename: str, width: int) -> str:
    local_file_original = f"{get_image_base_path()}/original/{filename}"
    local_file_resized = f"{get_image_base_path()}/w{width}/{filename}"
    if not os.path.exists(local_file_resized):
        if not os.path.exists(local_file_original):
            fetch_image(filename)
        resize_image(local_file_original, width, local_file_resized)

    return local_file_resized


def get_image_url(filename: str | None, width: int) -> str | None:
    if not filename:
        return None
    return f"/poster/{width}/{filename.lstrip('/')}"


def get_image_srcset(
    filename: str | None, widths: tuple[int, ...] = POSTER_WIDTHS
) -> str | None:
    """Build a `srcset` string listing each cached width as a candidate.

    Returns e.g. "/poster/185/x.jpg 185w, /poster/342/x.jpg 342w, ..." so the
    browser can pick the smallest source that fits the rendered size and DPR.
    """
    if not filename:
        return None
    cleaned = filename.lstrip("/")
    return ", ".join(f"/poster/{width}/{cleaned} {width}w" for width in widths)


def delete_local_poster(filename: str | None) -> None:
    """Remove the cached original and all resized variants of a poster file."""
    if not filename:
        return
    base_path = get_image_base_path()
    paths = [f"{base_path}/original/{filename}"]
    paths.extend(f"{base_path}/w{w}/{filename}" for w in POSTER_WIDTHS)
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            continue
        except OSError:
            _logger.exception("Failed to delete cached poster %s", path)


def prune_poster_cache(retention_days: int, dry_run: bool = False) -> dict:
    """Delete cached poster files unused for longer than the retention window.

    Eviction is based on ``max(atime, mtime)``: access time evicts by last use
    where the filesystem records it (``relatime``, the common default, keeps hot
    posters warm), degrading to modification time — which equals creation time
    for these write-once files — when atime is disabled (``noatime``). The cache
    is self-healing: a pruned poster is re-fetched and re-resized on its next
    request, so this only trades a little bandwidth to bound disk usage.

    Walks every width directory (``original/``, ``w200/`` ...). Best-effort:
    per-file errors are logged and skipped rather than aborting the sweep.
    Returns a summary dict for logging; with ``dry_run`` nothing is deleted.
    """
    base_path = get_image_base_path()
    cutoff = time.time() - retention_days * 86400
    scanned = deleted = bytes_freed = 0
    for root, _dirs, files in os.walk(base_path):
        for name in files:
            path = os.path.join(root, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            scanned += 1
            if max(stat.st_atime, stat.st_mtime) >= cutoff:
                continue
            if not dry_run:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    continue
                except OSError:
                    _logger.exception("Failed to prune cached poster %s", path)
                    continue
            deleted += 1
            bytes_freed += stat.st_size
    return {
        "scanned": scanned,
        "deleted": deleted,
        "bytes_freed": bytes_freed,
        "dry_run": dry_run,
    }


def prefetch_poster(filename: str | None) -> None:
    """Download and resize the poster so it is warm on disk before any request."""
    if not filename:
        return
    for width in POSTER_WIDTHS:
        try:
            ensure_image_exists(filename, width)
        except Exception:
            _logger.exception(
                "Failed to prefetch poster %s at width %s", filename, width
            )
