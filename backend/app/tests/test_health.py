def test_health_exposes_build_revision(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "development"}


def test_readiness_exposes_build_revision(client):
    response = client.get("/readiness")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "version": "development"}
