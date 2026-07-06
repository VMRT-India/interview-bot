async def test_health_infra_services_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()

    assert "status" in data
    assert "services" in data

    services = data["services"]
    # Core infra (Docker stack) must be healthy
    assert services["postgres"]["status"] == "ok"
    assert services["mongo"]["status"] == "ok"
    assert services["redis"]["status"] == "ok"
    assert services["qdrant"]["status"] == "ok"
    # Ollama may or may not be running; don't assert its status


async def test_health_response_structure(client):
    resp = await client.get("/health")
    data = resp.json()
    assert set(data["services"].keys()) == {"postgres", "mongo", "redis", "ollama", "qdrant"}
    for svc in data["services"].values():
        assert "status" in svc
        assert svc["status"] in ("ok", "error")
