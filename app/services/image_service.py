import os

import requests
from flask import current_app
from PIL import Image

from app.errors import ImageFetchError


def get_image_base_path() -> str:
    path = current_app.config.get("POSTER_DIR")
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def get_tmdb_image_base_url() -> str:
    return current_app.config.get("TMDB_IMAGE_BASE_URL").rstrip("/")


def get_tmdb_image_url(remote_filename: str) -> str:
    return f"{get_tmdb_image_base_url()}/{remote_filename}"


def fetch_image(remote_filename: str, size: str = "original"):
    target_filename = f"{get_image_base_path()}/{size}/{remote_filename}"
    remote_url = get_tmdb_image_url(remote_filename)
    response = requests.get(remote_url, timeout=10)
    if response.status_code != 200:
        raise ImageFetchError(f"Failed to fetch image from {remote_url}")
    os.makedirs(os.path.dirname(target_filename), exist_ok=True)
    with open(target_filename, "xb") as file:
        file.write(response.content)


def resize_image(original_file: str, width: int, target_filename: str):
    image = Image.open(original_file)
    image.thumbnail((width, width * 3))
    os.makedirs(os.path.dirname(target_filename), exist_ok=True)
    image.save(target_filename)


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
