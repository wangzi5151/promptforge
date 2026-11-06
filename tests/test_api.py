"""PromptForge API test suite."""
import importlib
import os
import tempfile

os.environ["PROMPTFORGE_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import db, main  # noqa: E402

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


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_get():
    r = client.post("/api/prompts", json=SAMPLE)
    assert r.status_code == 201
    p = r.json()
    assert p["title"] == "Test Prompt"
    assert p["variables"] == ["role", "task"]
    r2 = client.get(f"/api/prompts/{p['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == p["id"]


def test_list_and_search():
    r = client.get("/api/prompts", params={"q": "Test Prompt"})
    assert any(p["title"] == "Test Prompt" for p in r.json())
    r = client.get("/api/prompts", params={"category": "engineering"})
    assert all(p["category"] == "engineering" for p in r.json())


def test_update_bumps_version():
    p = client.post("/api/prompts", json=SAMPLE).json()
    r = client.patch(f"/api/prompts/{p['id']}", json={"body": "New body {{x}}"})
    assert r.status_code == 200
    assert r.json()["version"] == 2
    vs = client.get(f"/api/prompts/{p['id']}/versions").json()
    assert len(vs) == 2


def test_run_renders_variables():
    p = client.post("/api/prompts", json=SAMPLE).json()
    r = client.post(f"/api/prompts/{p['id']}/run", json={"variables": {"role": "chef", "task": "cook"}})
    assert "You are a chef." in r.json()["rendered"]
    assert "cook" in r.json()["rendered"]


def test_delete():
    p = client.post("/api/prompts", json=SAMPLE).json()
    assert client.delete(f"/api/prompts/{p['id']}").status_code == 200
    assert client.get(f"/api/prompts/{p['id']}").status_code == 404


def test_analytics():
    r = client.get("/api/analytics")
    assert r.status_code == 200
    assert "total_prompts" in r.json()


def test_api_keys_lifecycle():
    r = client.post("/api/api-keys", json={"label": "ci"})
    key = r.json()["key"]
    assert key.startswith("pf_")
    assert client.get("/api/api-keys").json()
    assert client.delete(f"/api/api-keys/{key}").status_code == 200


def test_spa_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "PromptForge" in r.text


def test_export():
    r = client.get("/api/export")
    assert r.status_code == 200
