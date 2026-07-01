def test_health_endpoint_works(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "b2b-ai-order-processing-agent"}
