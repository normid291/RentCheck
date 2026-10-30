"""Page-level layout routing: public pages for guests, app shell for members."""
from __future__ import annotations

from urllib.parse import quote

from conftest import requires_db

pytestmark = requires_db

APP_ROUTES = ["/dashboard", "/history", "/profile", "/dashboard/new"]


def test_guest_public_pages_and_app_guards(client):
    landing = client.get("/", follow_redirects=False)
    assert landing.status_code == 200
    assert "text/html" in landing.headers["content-type"]

    analyser = client.get("/analyse", follow_redirects=False)
    assert analyser.status_code == 200
    assert "text/html" in analyser.headers["content-type"]

    for path in ("/privacy", "/terms"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200
        assert 'data-shell="sidebar"' not in response.text

    for path in APP_ROUTES:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login?next=" + quote(path, safe="")

    raw_app = client.get("/dashboard.html", follow_redirects=False)
    assert raw_app.status_code == 303
    assert raw_app.headers["location"] == "/dashboard"

    raw_guest = client.get("/analyse.html", follow_redirects=False)
    assert raw_guest.status_code == 303
    assert raw_guest.headers["location"] == "/analyse"

    assert client.get("/not-a-page.html", follow_redirects=False).status_code == 404


def test_member_is_sent_to_app_shell(client, make_user):
    make_user()

    landing = client.get("/", follow_redirects=False)
    assert landing.status_code == 303
    assert landing.headers["location"] == "/dashboard"

    analyser = client.get("/analyse", follow_redirects=False)
    assert analyser.status_code == 303
    assert analyser.headers["location"] == "/dashboard/new"

    for path in APP_ROUTES:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    for path in ("/privacy", "/terms"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200
        assert 'data-shell="sidebar"' in response.text
        assert "<article>" in response.text
