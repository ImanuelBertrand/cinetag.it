import os
from unittest.mock import MagicMock, mock_open, patch

from app.services.image_service import (
    ensure_image_exists,
    fetch_image,
    get_image_base_path,
    get_image_url,
    get_tmdb_image_base_url,
    get_tmdb_image_url,
    resize_image,
)


def test_get_image_base_path(app):
    """Test that get_image_base_path returns the correct path."""
    with app.app_context():
        # Configure a test path
        app.config["POSTER_DIR"] = "/test/path"

        # Mock os.path.exists and os.makedirs to avoid file system operations
        with patch("os.path.exists", return_value=True), patch("os.makedirs"):
            path = get_image_base_path()
            assert path == "/test/path"


def test_get_image_base_path_creates_directory(app):
    """Test that get_image_base_path creates the directory if it doesn't exist."""
    with app.app_context():
        # Configure a test path
        app.config["POSTER_DIR"] = "/test/path"

        # Mock os.path.exists to return False and check if os.makedirs is called
        with (
            patch("os.path.exists", return_value=False) as mock_exists,
            patch("os.makedirs") as mock_makedirs,
        ):
            path = get_image_base_path()
            assert path == "/test/path"
            mock_exists.assert_called_once_with("/test/path")
            mock_makedirs.assert_called_once_with("/test/path")


def test_get_tmdb_image_base_url(app):
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


def test_get_tmdb_image_url(app):
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


def test_get_image_url():
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


def test_fetch_image(app):
    """Test that fetch_image downloads and saves an image."""
    with app.app_context():
        # Configure test paths
        app.config["POSTER_DIR"] = "/test/path"
        app.config["TMDB_IMAGE_BASE_URL"] = "https://image.tmdb.org/t/p"

        # Mock the necessary functions
        with (
            patch(
                "app.services.image_service.get_image_base_path",
                return_value="/test/path",
            ),
            patch(
                "app.services.image_service.get_tmdb_image_url",
                return_value="https://image.tmdb.org/t/p/test/image.jpg",
            ),
            patch("requests.get") as mock_get,
            patch("os.makedirs") as mock_makedirs,
            patch("builtins.open", mock_open()) as mock_file,
        ):
            # Configure the mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"test image content"
            mock_get.return_value = mock_response

            # Call the function
            fetch_image("test/image.jpg")

            # Verify the function called the expected methods
            mock_get.assert_called_once_with(
                "https://image.tmdb.org/t/p/test/image.jpg", timeout=10
            )
            mock_makedirs.assert_called_once_with(
                os.path.dirname("/test/path/original/test/image.jpg"), exist_ok=True
            )
            mock_file.assert_called_once_with(
                "/test/path/original/test/image.jpg", "xb"
            )
            mock_file().write.assert_called_once_with(b"test image content")


def test_resize_image():
    """Test that resize_image resizes an image correctly."""
    # Mock the necessary functions
    with patch("PIL.Image.open") as mock_open, patch("os.makedirs") as mock_makedirs:
        # Configure the mock image
        mock_image = MagicMock()
        mock_open.return_value = mock_image

        # Call the function
        resize_image("/test/original.jpg", 500, "/test/resized.jpg")

        # Verify the function called the expected methods
        mock_open.assert_called_once_with("/test/original.jpg")
        mock_image.thumbnail.assert_called_once_with((500, 1500))
        mock_makedirs.assert_called_once_with(
            os.path.dirname("/test/resized.jpg"), exist_ok=True
        )
        mock_image.save.assert_called_once_with("/test/resized.jpg")


def test_ensure_image_exists_already_present(app):
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


def test_ensure_image_exists_triggers_resize(app):
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


def test_ensure_image_exists_triggers_fetch_and_resize(app):
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
