from __future__ import annotations


def test_system_health_and_metrics_endpoints(client):
    test_client, _session_factory = client

    health_response = test_client.get("/api/system/health")
    assert health_response.status_code == 200
    assert health_response.json()["database"]["ok"] is True

    ai_status_response = test_client.get("/api/system/ai-status")
    assert ai_status_response.status_code == 200
    assert "ocr" in ai_status_response.json()

    integrations_response = test_client.get("/api/system/integrations")
    assert integrations_response.status_code == 200
    assert "esign" in integrations_response.json()
    assert integrations_response.json()["integrations"]

    metrics_response = test_client.get("/api/system/metrics")
    assert metrics_response.status_code == 200
    assert "request_totals" in metrics_response.json()

    prometheus_response = test_client.get("/api/system/metrics/prometheus")
    assert prometheus_response.status_code == 200
    assert "xai_http_requests_total" in prometheus_response.text
