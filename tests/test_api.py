"""PromptForge API test suite."""
import importlib
import os
import tempfile

os.environ["PROMPTFORGE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["PROMPTFORGE_REQUIRE_KEY"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db, llm, main  # noqa: E402

importlib.reload(db)
db.init_db()
client = TestClient(main.app)

SAMPLE = {
    "title": "Test Prompt",
    "body": "You are a {{role}}. Task: {{task}}",
    "category": "engineering",
    "tags": ["test"],
    "description": "a test",
}


# ----------------------------- basics -----------------------------

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "llm_ready" in body


def test_seed_templates_present():
    prompts = client.get("/api/prompts").json()
    assert len(prompts) >= 10
    assert any(p["title"] == "Senior Code Reviewer" for p in prompts)


def test_create_get_update_flow():
    p = client.post("/api/prompts", json=SAMPLE).json()
    assert p["title"] == "Test Prompt"
    # variables keep order of appearance, not alphabetical
    assert p["variables"] == ["role", "task"]

    got = client.get(f"/api/prompts/{p['id']}").json()
    assert got["id"] == p["id"]

    upd = client.patch(f"/api/prompts/{p['id']}", json={"body": "New {{x}} body"}).json()
    assert upd["version"] == 2
    assert upd["variables"] == ["x"]


def test_search_and_filters():
    client.post("/api/prompts", json={**SAMPLE, "title": "Unique Zebra Prompt"})
    r = client.get("/api/prompts", params={"q": "Zebra"})
    assert any("Zebra" in p["title"] for p in r.json())

    r = client.get("/api/prompts", params={"category": "engineering"})
    assert r.json() and all(p["category"] == "engineering" for p in r.json())

    cats = client.get("/api/categories").json()
    assert "engineering" in cats


def test_favorite_toggle():
    p = client.post("/api/prompts", json=SAMPLE).json()
    r = client.post(f"/api/prompts/{p['id']}/favorite").json()
    assert r["favorite"] is True
    r = client.post(f"/api/prompts/{p['id']}/favorite").json()
    assert r["favorite"] is False


def test_versions_and_restore():
    p = client.post("/api/prompts", json=SAMPLE).json()
    v1_body = p["body"]
    client.patch(f"/api/prompts/{p['id']}", json={"body": "second version"})

    vs = client.get(f"/api/prompts/{p['id']}/versions").json()
    assert [v["version"] for v in vs] == [2, 1]

    d = client.get(f"/api/prompts/{p['id']}/versions/2/diff").json()
    assert "+second version" in d["diff"]

    restored = client.post(f"/api/prompts/{p['id']}/versions/1/restore").json()
    assert restored["body"] == v1_body
    assert restored["version"] == 3


def test_delete_cascade():
    p = client.post("/api/prompts", json=SAMPLE).json()
    client.post(f"/api/prompts/{p['id']}/run", json={"variables": {}})
    assert client.delete(f"/api/prompts/{p['id']}").status_code == 200
    assert client.get(f"/api/prompts/{p['id']}").status_code == 404


# ----------------------------- runs -----------------------------

def test_render_without_llm():
    p = client.post("/api/prompts", json=SAMPLE).json()
    r = client.post(f"/api/prompts/{p['id']}/run",
                    json={"variables": {"role": "chef", "task": "cook"}, "call_llm": False})
    assert r.status_code == 200
    assert "You are a chef." in r.json()["rendered"]


def test_render_keeps_unknown_vars():
    p = client.post("/api/prompts", json=SAMPLE).json()
    r = client.post(f"/api/prompts/{p['id']}/run", json={"variables": {"role": "x"}, "call_llm": False})
    assert "{{task}}" in r.json()["rendered"]


def test_run_with_mock_llm():
    """No API key configured -> deterministic mock, still exercises the pipeline."""
    p = client.post("/api/prompts", json=SAMPLE).json()
    r = client.post(f"/api/prompts/{p['id']}/run",
                    json={"variables": {"role": "dev", "task": "ship"}, "call_llm": True})
    assert r.status_code == 200
    body = r.json()
    assert body["mocked"] is True
    assert body["output"]


def test_score_run():
    p = client.post("/api/prompts", json=SAMPLE).json()
    r = client.post(f"/api/prompts/{p['id']}/run", json={"variables": {}, "call_llm": True}).json()
    assert client.post(f"/api/runs/{r['id']}/score", json={"score": 4}).status_code == 200
    runs = client.get(f"/api/prompts/{p['id']}/runs").json()
    assert runs[0]["score"] == 4


def test_score_validation():
    assert client.post("/api/runs/nope/score", json={"score": 4}).status_code == 404
    p = client.post("/api/prompts", json=SAMPLE).json()
    r = client.post(f"/api/prompts/{p['id']}/run", json={"variables": {}}).json()
    assert client.post(f"/api/runs/{r['id']}/score", json={"score": 9}).status_code == 422


def test_analytics_shape():
    a = client.get("/api/analytics").json()
    for k in ("total_prompts", "total_runs", "by_category", "trend", "top_prompts", "avg_score"):
        assert k in a


# ----------------------------- providers -----------------------------

def test_provider_crud():
    providers = client.get("/api/providers").json()
    assert len(providers) >= 3
    assert all("api_key" not in p for p in providers), "api_key must never leak"

    created = client.post("/api/providers", json={
        "name": "Mock", "base_url": "https://example.com/v1", "model": "m", "api_key": "sk-test"
    }).json()
    assert created["has_key"] is True
    assert "api_key" not in created

    assert client.post(f"/api/providers/{created['id']}/activate").status_code == 200
    active = [p for p in client.get("/api/providers").json() if p["is_active"]]
    assert len(active) == 1 and active[0]["id"] == created["id"]

    assert client.delete(f"/api/providers/{created['id']}").status_code == 200


# ----------------------------- io -----------------------------

def test_export_import_roundtrip():
    exported = client.get("/api/export").json()
    assert "prompts" in exported and exported["prompts"]
    before = len(client.get("/api/prompts").json())
    r = client.post("/api/import", json={"prompts": exported["prompts"][:2]}).json()
    assert r["imported"] == 2
    assert len(client.get("/api/prompts").json()) == before + 2


def test_import_skips_invalid():
    r = client.post("/api/import", json={"prompts": [{"title": "no body"}, {"body": "no title"}]}).json()
    assert r["imported"] == 0


# ----------------------------- api keys -----------------------------

def test_api_keys():
    key = client.post("/api/api-keys", json={"label": "ci"}).json()["key"]
    assert key.startswith("pf_")
    assert any(k["key"] == key for k in client.get("/api/api-keys").json())
    assert client.delete(f"/api/api-keys/{key}").status_code == 200


def test_require_api_key_enforced(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "REQUIRE_API_KEY", True)
    assert client.post("/api/prompts", json=SAMPLE).status_code == 401
    key = db.create_api_key("test")["key"]
    assert client.post("/api/prompts", json=SAMPLE, headers={"X-API-Key": key}).status_code == 201


# ----------------------------- unit -----------------------------

@pytest.mark.parametrize("body,expected", [
    ("{{a}} and {{b}}", ["a", "b"]),
    ("{{ a }} {{a}}", ["a"]),
    ("no vars", []),
    ("{{snake_case_1}}", ["snake_case_1"]),
])
def test_extract_vars(body, expected):
    assert main.extract_vars(body) == expected


def test_rough_token_estimate():
    assert llm._rough_tokens("") >= 1
    assert llm._rough_tokens("a" * 400) == 100
    assert llm._rough_tokens("中文中文") == 4


def test_spa_assets_served():
    assert client.get("/").status_code == 200
    assert "PromptForge" in client.get("/").text
    assert client.get("/app.css").status_code == 200
    assert client.get("/app.js").status_code == 200
