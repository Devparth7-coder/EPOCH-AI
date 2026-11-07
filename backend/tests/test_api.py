import time


def _wait(client, research_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = client.get(f"/api/v1/research/{research_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in {"succeeded", "failed"}:
            return body
        time.sleep(0.2)
    raise AssertionError("research did not finish in time")


def test_health_and_meta(client):
    health = client.get("/api/v1/system/health").json()
    assert health["status"] == "healthy"
    assert health["runtime_mode"] in {"live", "hybrid", "simulated"}
    assert health["providers"]["tavily"]["configured"] is False
    meta = client.get("/api/v1/meta").json()
    assert "VERDICTS" not in meta["verdicts"]
    assert len(meta["verdicts"]) == 6


def test_claims_preview(client):
    resp = client.post(
        "/api/v1/claims/preview",
        json={"content": "Python 3.7 is the newest version of Python. React 19 was released in December 2024."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["count"] >= 2
    assert body["claims"][0]["text"]


def test_validation_errors_are_structured(client):
    resp = client.post("/api/v1/research", json={"content": "no"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
    assert resp.json()["error"]["request_id"]


def test_oversized_input_rejected(client):
    resp = client.post("/api/v1/research", json={"content": "a" * 21000})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_ssrf_url_rejected(client):
    resp = client.post(
        "/api/v1/research", json={"content": "http://127.0.0.1:8000/admin", "input_type": "url"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsafe_url"


def test_full_research_flow(client):
    payload = {
        "content": (
            "Python 3.7 is the newest version of Python and should be used for all new projects. "
            "React 19 was released in December 2024. "
            "The EU AI Act entered into force on August 1, 2024."
        ),
        "depth": "standard",
        "run_synchronously": True,
    }
    created = client.post("/api/v1/research", json=payload)
    assert created.status_code == 201
    research_id = created.json()["research_id"]

    body = _wait(client, research_id)
    assert body["status"] == "succeeded", body["error"]
    assert len(body["stage_states"]) == 6
    assert all(s["status"] == "done" for s in body["stage_states"])
    assert body["claim_count"] >= 3
    assert body["evidence_count"] >= 1
    assert body["overall_verdict"] in {
        "VERIFIED", "PARTIALLY_OUTDATED", "OUTDATED", "CONTRADICTED", "UNVERIFIED", "CONFLICTING"
    }
    assert body["metrics"]["pipeline_latency_ms"] > 0
    assert all(c["verdict"] for c in body["claims"])

    verdicts = {c["text"][:20]: c["verdict"]["verdict"] for c in body["claims"]}
    assert any(v in {"OUTDATED", "CONTRADICTED", "PARTIALLY_OUTDATED"} for v in verdicts.values())

    evidence = client.get(f"/api/v1/research/{research_id}/evidence").json()
    assert evidence["graph"]["counts"]["claims"] >= 3
    assert evidence["graph"]["nodes"] and evidence["graph"]["links"]

    report = client.get(f"/api/v1/research/{research_id}/report").json()
    assert report["overall_verdict"] == body["overall_verdict"]
    assert report["sources"] and report["sources"][0]["url"].startswith("http")
    assert report["limitations"] is not None
    assert report["calibration"]["trained_on"]


def test_history_filters_and_analytics(client):
    history = client.get("/api/v1/history?limit=5").json()
    assert history["total"] >= 1
    assert len(history["items"]) <= 5

    filtered = client.get("/api/v1/history?status=succeeded").json()
    assert all(item["status"] == "succeeded" for item in filtered["items"])

    analytics = client.get("/api/v1/analytics").json()
    assert analytics["totals"]["claims_analyzed"] >= 3
    assert analytics["totals"]["sources_retrieved"] >= 1
    assert len(analytics["activity"]) == 14
    assert analytics["quality"]["mean_evidence_quality"] >= 0


def test_observability_reports_measured_values(client):
    obs = client.get("/api/v1/system/observability").json()
    assert obs["research"]["by_status"]
    assert obs["usage"]["total_calls"] >= 0
    assert "stage_latency_ms" in obs
    assert obs["model_routing"]["observed_routes"]


def test_not_found_is_structured(client):
    resp = client.get("/api/v1/research/rs_missing")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
