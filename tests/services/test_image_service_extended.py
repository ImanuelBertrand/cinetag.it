from unittest.mock import patch

import pytest

from app.services.image_service import (
    ensure_image_exists,
    fetch_image,
    get_image_url,
    resize_image,
)


def test_fetch_image_non_200_does_not_write(app, tmp_path):
    with app.app_context():
        app.config["POSTER_DIR"] = str(tmp_path)
        with patch("app.services.image_service.requests.get") as mget:
            mget.return_value.status_code = 404
            mget.return_value.content = b""
            with pytest.raises(Exception, match="Failed to fetch image"):
                fetch_image("x/y.jpg")
        # no file created
        assert not (tmp_path / "original" / "x" / "y.jpg").exists()


def test_fetch_image_existing_file_is_overwritten(app, tmp_path):
    """A concurrent fetcher (or stale leftover) is replaced atomically.

    TMDB filenames are content-addressed so the new bytes equal the old bytes
    in practice; overwriting is safe and prevents FileExistsError from being
    surfaced to a user request under threading.
    """
    with app.app_context():
        app.config["POSTER_DIR"] = str(tmp_path)
        target = tmp_path / "original" / "x" / "y.jpg"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"abc")
        with patch("app.services.image_service.requests.get") as mget:
            mget.return_value.status_code = 200
            mget.return_value.content = b"xyz"
            fetch_image("x/y.jpg")
        assert target.read_bytes() == b"xyz"
        # No .tmp file left around after a successful fetch.
        assert not list(target.parent.glob("*.tmp"))


def test_fetch_image_cleans_up_tmp_on_write_error(app, tmp_path):
    """If the write fails mid-way, the tmp file is removed."""
    with app.app_context():
        app.config["POSTER_DIR"] = str(tmp_path)
        with (
            patch("app.services.image_service.requests.get") as mget,
            patch(
                "app.services.image_service.os.replace",
                side_effect=OSError("disk full"),
            ),
        ):
            mget.return_value.status_code = 200
            mget.return_value.content = b"xyz"
            with pytest.raises(OSError, match="disk full"):
                fetch_image("x/y.jpg")
        target_dir = tmp_path / "original" / "x"
        assert not list(target_dir.glob("*.tmp"))
        assert not (target_dir / "y.jpg").exists()


def test_resize_image_non_image_raises(tmp_path):
    src = tmp_path / "orig.bin"
    src.write_bytes(b"not-an-image")
    dst = tmp_path / "w100" / "x.jpg"
    # PIL.Image.open should raise UnidentifiedImageError or similar
    from PIL import UnidentifiedImageError

    with pytest.raises(UnidentifiedImageError):
        resize_image(str(src), 100, str(dst))
    assert not dst.exists()


def test_get_image_url_strips_multiple_leading_slashes():
    assert get_image_url("//path/to.jpg", 200) == "/poster/200/path/to.jpg"
    assert get_image_url("/one.jpg", 10) == "/poster/10/one.jpg"
    assert get_image_url("", 10) is None


def test_get_image_contents_fetch_fails_bubbles_up(app, tmp_path):
    with app.app_context():
        app.config["POSTER_DIR"] = str(tmp_path)
        with (
            patch(
                "app.services.image_service.fetch_image", side_effect=Exception("boom")
            ),
            pytest.raises(Exception, match="boom"),
        ):
            ensure_image_exists("x.jpg", 200)
        # Ensure no partial file is left behind in w200
        # (original might not even be attempted if fetch_image fails)
        assert not (tmp_path / "original" / "x.jpg").exists()
        assert not (tmp_path / "w200" / "x.jpg").exists()
