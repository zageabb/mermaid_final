from app import app


def test_uda_prefix_is_used_for_navigation_and_actions():
    client = app.test_client()
    headers = {
        "X-Forwarded-Prefix": "/apps/mermaid-display-app",
        "X-Forwarded-Host": "tanyaanne.ddns.net",
        "X-Forwarded-Proto": "https",
    }

    response = client.get("/", headers=headers)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'href="/apps/mermaid-display-app/"' in html
    assert 'href="/apps/mermaid-display-app/repository"' in html
    assert 'action="/apps/mermaid-display-app/save"' in html
