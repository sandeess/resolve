from fastapi.testclient import TestClient

API = "/api/v1"


def test_unknown_api_paths_answer_json_404(client: TestClient) -> None:
    """The web app's index page must never answer an API request."""
    for method in ("get", "post", "put", "patch", "delete"):
        response = getattr(client, method)(f"{API}/no-such-endpoint")
        assert response.status_code == 404, method
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": "Not Found"}


def test_known_api_paths_still_win_over_the_catch_all(client: TestClient) -> None:
    assert client.get(f"{API}/utils/health-check/").status_code == 200
