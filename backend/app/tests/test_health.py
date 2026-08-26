def test_health_exposes_build_revision(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "development"}


def test_readiness_exposes_build_revision(client):
    response = client.get("/readiness")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "version": "development"}


def test_deep_ai_readiness_exercises_active_provider(client):
    response = client.get("/readiness/ai/deep")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ready"
    assert "Embedding" in response.json()["details"]
    assert "completion" in response.json()["details"]
