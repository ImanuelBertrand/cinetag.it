import os
import time
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services.image_service import (
    POSTER_JPEG_QUALITY,
    ensure_image_exists,
    fetch_image,
    get_image_base_path,
    get_image_url,
    get_tmdb_image_base_url,
    get_tmdb_image_url,
    negotiate_poster_format,
    poster_mime_type,
    prune_poster_cache,
    resize_image,
)


def test_get_image_base_path(app) -> None:
    """Test that get_image_base_path returns the correct path."""
    with app.app_context():
        # Configure a test path
        app.config["POSTER_DIR"] = "/test/path"

        # Mock os.path.exists and os.makedirs to avoid file system operations
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            path = get_image_base_path()
            assert path == "/test/path"


def test_get_image_base_path_creates_directory(app) -> None:
    """Test that get_image_base_path ensures the directory exists.

    We rely on os.makedirs(..., exist_ok=True), which is idempotent under
    threading (no TOCTOU between exists() and makedirs()).
    """
    with app.app_context():
        app.config["POSTER_DIR"] = "/test/path"

        with patch("os.makedirs") as mock_makedirs:
            path = get_image_base_path()
            assert path == "/test/path"
            mock_makedirs.assert_called_once_with("/test/path", exist_ok=True)


def test_get_tmdb_image_base_url(app) -> None:
    """Test that get_tmdb_image_base_url returns the correct URL."""
    with app.app_context():
        # Configure a test URL
        app.config["TMDB_IMAGE_BASE_URL"] = "https://image.tmdb.org/t/p"

        url = get_tmdb_image_base_url()
        assert url == "https://image.tmdb.org/t/p"

        # Test with trailing slash
        app.config["TMDB_IMAGE_BASE_URL"] = "https://image.tmdb.org/t/p/"
        url = get_tmdb_image_base_url()
        assert url == "https://image.tmdb.org/t/p"


def test_get_tmdb_image_url(app) -> None:
    """Test that get_tmdb_image_url constructs the correct URL."""
    with app.app_context():
        # Configure a test URL
        app.config["TMDB_IMAGE_BASE_URL"] = "https://image.tmdb.org/t/p"

        # Test with a path that has a leading slash
        url = get_tmdb_image_url("/test/image.jpg")
        assert url == "https://image.tmdb.org/t/p//test/image.jpg"

        # Test with a path that doesn't have a leading slash
        url = get_tmdb_image_url("test/image.jpg")
        assert url == "https://image.tmdb.org/t/p/test/image.jpg"


def test_get_image_url() -> None:
    """Test that get_image_url constructs the correct URL."""
    # Test with a valid filename
    url = get_image_url("/test/image.jpg", 500)
    assert url == "/poster/500/test/image.jpg"

    # Test with a filename that has a leading slash
    url = get_image_url("/test/image.jpg", 300)
    assert url == "/poster/300/test/image.jpg"

    # Test with None
    url = get_image_url(None, 500)
    assert url is None


def test_fetch_image(app, tmp_path) -> None:
    """Test that fetch_image downloads and atomically writes an image."""
    with app.app_context():
        app.config["POSTER_DIR"] = str(tmp_path)
        app.config["TMDB_IMAGE_BASE_URL"] = "https://image.tmdb.org/t/p"

        with patch("app.services.image_service.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"test image content"
            mock_get.return_value = mock_response

            fetch_image("test/image.jpg")

            mock_get.assert_called_once_with(
                "https://image.tmdb.org/t/p/test/image.jpg", timeout=10
            )
            target = tmp_path / "original" / "test" / "image.jpg"
            assert target.read_bytes() == b"test image content"
            # No stray .tmp files left behind in the target directory.
            assert not list(target.parent.glob("*.tmp"))


def test_resize_image() -> None:
    """Test that resize_image resizes and atomically writes the result."""
    with (
        patch("PIL.Image.open") as mock_open,
        patch("os.makedirs") as mock_makedirs,
        patch("os.replace") as mock_replace,
    ):
        mock_image = MagicMock()
        mock_open.return_value = mock_image

        resize_image("/test/original.jpg", 500, "/test/resized.jpg")

        mock_open.assert_called_once_with("/test/original.jpg")
        mock_image.thumbnail.assert_called_once_with(
            (500, 1500), resample=Image.Resampling.LANCZOS
        )
        mock_makedirs.assert_called_once_with(
            os.path.dirname("/test/resized.jpg"), exist_ok=True
        )
        # PIL saves to a tmp filename ending in the original extension,
        # which is then atomically renamed onto the target.
        save_args = mock_image.save.call_args.args
        assert len(save_args) == 1
        assert mock_image.save.call_args.kwargs["quality"] == POSTER_JPEG_QUALITY
        tmp_path = save_args[0]
        assert tmp_path.startswith("/test/resized.jpg.")
        assert tmp_path.endswith(".jpg")
        mock_replace.assert_called_once_with(tmp_path, "/test/resized.jpg")


def test_ensure_image_exists_already_present(app) -> None:
    """Test that ensure_image_exists returns the path immediately if file exists."""
    with app.app_context():
        # Configure test paths
        app.config["POSTER_DIR"] = "/test/path"

        # Mock the necessary functions
        with (
            patch(
                "app.services.image_service.get_image_base_path",
                return_value="/test/path",
            ),
            patch("os.path.exists", return_value=True),
        ):
            path = ensure_image_exists("test/image.jpg", 500)

            assert path == "/test/path/w500/test/image.jpg"


def test_ensure_image_exists_triggers_resize(app) -> None:
    """Test that ensure_image_exists triggers resize
    if original exists but resized doesn't."""
    with app.app_context():
        # Configure test paths
        app.config["POSTER_DIR"] = "/test/path"

        # Mock the necessary functions
        with (
            patch(
                "app.services.image_service.get_image_base_path",
                return_value="/test/path",
            ),
            patch("os.path.exists", side_effect=[False, True]),
            patch("app.services.image_service.resize_image") as mock_resize,
        ):
            path = ensure_image_exists("test/image.jpg", 500)

            assert path == "/test/path/w500/test/image.jpg"
            mock_resize.assert_called_once_with(
                "/test/path/original/test/image.jpg",
                500,
                "/test/path/w500/test/image.jpg",
            )


def test_ensure_image_exists_triggers_fetch_and_resize(app) -> None:
    """Test that ensure_image_exists fetches and
    resizes the image when neither exists."""
    with app.app_context():
        # Configure test paths
        app.config["POSTER_DIR"] = "/test/path"

        # Mock the necessary functions
        with (
            patch(
                "app.services.image_service.get_image_base_path",
                return_value="/test/path",
            ),
            patch("os.path.exists", side_effect=[False, False]),
            patch("app.services.image_service.fetch_image") as mock_fetch,
            patch("app.services.image_service.resize_image") as mock_resize,
        ):
            path = ensure_image_exists("test/image.jpg", 500)

            assert path == "/test/path/w500/test/image.jpg"
            mock_fetch.assert_called_once_with("test/image.jpg")
            mock_resize.assert_called_once_with(
                "/test/path/original/test/image.jpg",
                500,
                "/test/path/w500/test/image.jpg",
            )


def test_prune_poster_cache_removes_only_stale_files(app, tmp_path) -> None:
    """Files unused past the window are pruned; recently-used ones are kept."""
    with app.app_context():
        app.config["POSTER_DIR"] = str(tmp_path)
        (tmp_path / "w500").mkdir()
        (tmp_path / "original").mkdir()

        stale = tmp_path / "w500" / "stale.jpg"
        stale.write_bytes(b"x" * 100)
        recent = tmp_path / "w500" / "recent.jpg"
        recent.write_bytes(b"y" * 50)
        hot = tmp_path / "original" / "hot.jpg"
        hot.write_bytes(b"z" * 200)

        now = time.time()
        old = now - 40 * 86400
        # Both timestamps old -> pruned.
        os.utime(stale, (old, old))
        # Modified recently -> kept (covers the noatime / creation-time case).
        os.utime(recent, (now, now))
        # Created long ago but accessed recently -> kept via atime.
        os.utime(hot, (now, old))

        result = prune_poster_cache(retention_days=30, dry_run=False)

        assert not stale.exists()
        assert recent.exists()
        assert hot.exists()
        assert result == {
            "scanned": 3,
            "deleted": 1,
            "bytes_freed": 100,
            "dry_run": False,
        }


def test_prune_poster_cache_dry_run_deletes_nothing(app, tmp_path) -> None:
    """dry_run reports what would be pruned without touching the filesystem."""
    with app.app_context():
        app.config["POSTER_DIR"] = str(tmp_path)
        (tmp_path / "w500").mkdir()
        stale = tmp_path / "w500" / "stale.jpg"
        stale.write_bytes(b"x" * 100)
        old = time.time() - 40 * 86400
        os.utime(stale, (old, old))

        result = prune_poster_cache(retention_days=30, dry_run=True)

        assert stale.exists()
        assert result["deleted"] == 1
        assert result["bytes_freed"] == 100
        assert result["dry_run"] is True


def test_negotiate_poster_format() -> None:
    """AVIF is preferred over WebP; anything not explicitly named -> None."""
    assert negotiate_poster_format("image/avif,image/webp,*/*") == "avif"
    assert negotiate_poster_format("image/webp,*/*") == "webp"
    assert negotiate_poster_format("*/*") is None
    assert negotiate_poster_format("") is None
    assert negotiate_poster_format(None) is None


def test_poster_mime_type() -> None:
    """Content-Type is derived from the (last) extension of the served file."""
    assert poster_mime_type("a.jpg") == "image/jpeg"
    assert poster_mime_type("a.jpg.webp") == "image/webp"
    assert poster_mime_type("a.jpg.avif") == "image/avif"
    with pytest.raises(ValueError, match="Unsupported file type"):
        poster_mime_type("a.txt")


def test_ensure_image_exists_format_variant(app) -> None:
    """A format variant is cached alongside as w{width}/{filename}.{fmt}."""
    with app.app_context():
        app.config["POSTER_DIR"] = "/test/path"
        with (
            patch(
                "app.services.image_service.get_image_base_path",
                return_value="/test/path",
            ),
            patch("os.path.exists", side_effect=[False, True]),
            patch("app.services.image_service.resize_image") as mock_resize,
        ):
            path = ensure_image_exists("test/image.jpg", 500, "webp")

            assert path == "/test/path/w500/test/image.jpg.webp"
            mock_resize.assert_called_once_with(
                "/test/path/original/test/image.jpg",
                500,
                "/test/path/w500/test/image.jpg.webp",
            )


def test_resize_image_encodes_by_extension(tmp_path) -> None:
    """resize_image infers the output codec from the target extension."""
    src = tmp_path / "src.jpg"
    Image.new("RGB", (1000, 1500), (100, 50, 25)).save(src, quality=90)

    for ext, pil_format in ((".jpg", "JPEG"), (".webp", "WEBP"), (".avif", "AVIF")):
        target = tmp_path / f"out{ext}"
        resize_image(str(src), 300, str(target))
        assert target.exists()
        with Image.open(target) as im:
            assert im.format == pil_format
            assert im.width == 300


def test_get_poster_negotiates_format(app, client) -> None:
    """The route serves the negotiated variant with a Vary: Accept header."""
    with patch("app.routes.html.ensure_image_exists") as mock_ensure:
        # AVIF-capable browser
        resp = client.get(
            "/poster/500/abc.jpg", headers={"Accept": "image/avif,image/webp,*/*"}
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/avif"
        assert resp.headers["X-Accel-Redirect"] == "/internal-static/w500/abc.jpg.avif"
        assert resp.headers["Vary"] == "Accept"
        mock_ensure.assert_called_once_with("abc.jpg", 500, "avif")

        # Legacy browser -> original format, no suffix
        mock_ensure.reset_mock()
        resp = client.get("/poster/500/abc.jpg", headers={"Accept": "*/*"})
        assert resp.headers["Content-Type"] == "image/jpeg"
        assert resp.headers["X-Accel-Redirect"] == "/internal-static/w500/abc.jpg"
        mock_ensure.assert_called_once_with("abc.jpg", 500, None)


def test_get_poster_rejects_invalid_width(client) -> None:
    resp = client.get("/poster/999/abc.jpg", headers={"Accept": "*/*"})
    assert resp.status_code == 400
