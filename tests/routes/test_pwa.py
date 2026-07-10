import json


def test_manifest_is_served_and_valid(client) -> None:
    """The web manifest is reachable and is valid JSON with icons."""
    response = client.get("/static/manifest.webmanifest")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["name"] == "CineTagIt"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    sizes = {icon["sizes"] for icon in data["icons"]}
    assert {"192x192", "512x512"} <= sizes
    assert any(icon.get("purpose") == "maskable" for icon in data["icons"])


def test_pages_link_manifest_and_theme_color(client) -> None:
    """Every page advertises the manifest and a theme color for installability."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"manifest.webmanifest" in response.data
    assert b'name="theme-color"' in response.data
    assert b"apple-touch-icon" in response.data


def test_service_worker_served(client) -> None:
    """The service worker is served at the app root scope."""
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert b"notificationclick" in response.data
