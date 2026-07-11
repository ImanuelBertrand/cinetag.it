import os
from unittest.mock import MagicMock, patch

from PIL import Image

from app.services.image_service import (
    POSTER_JPEG_QUALITY,
    ensure_image_exists,
    fetch_image,
    get_image_base_path,
    get_image_url,
    get_tmdb_image_base_url,
    get_tmdb_image_url,
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
