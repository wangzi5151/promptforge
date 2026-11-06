"""PromptForge — open-source prompt engineering workbench.

FastAPI application exposing a REST API plus the built-in SPA.
"""
import json
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, config, db, llm

VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="PromptForge API",
    version=__version__,
    description="Open-source prompt engineering workbench — compose, version, evaluate and ship prompts.",
    contact={"name": "PromptForge", "url": "https://github.com/wangzi5151/promptforge"},
    license_info={"name": "MIT"},
    lifespan=lifespan,
)


# ------------------------------- schemas -------------------------------

class PromptIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1)
    category: str = "general"
    tags: list[str] = []
    description: str = ""
    model_hint: str = ""
    favorite: bool = False


class PromptPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    description: str | None = None
    model_hint: str | None = None
    favorite: bool | None = None
    change_note: str = ""


class RunIn(BaseModel):
    variables: dict[str, str] = {}
    prompt_body: str | None = None
    model: str | None = None
    call_llm: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class CompareIn(BaseModel):
    variables: dict[str, str] = {}
    body_a: str
    body_b: str
    model: str | None = None


class ScoreIn(BaseModel):
    score: int = Field(ge=1, le=5)
    feedback: str = ""


class ProviderIn(BaseModel):
    id: str | None = None
    name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    is_active: bool | None = None


class ApiKeyIn(BaseModel):
    label: str = ""


class ImportIn(BaseModel):
    prompts: list[dict] = []


# ------------------------------- helpers -------------------------------

def render(body: str, variables: dict) -> str:
    return VAR_PATTERN.sub(lambda m: str(variables.get(m.group(1), m.group(0))), body)


def extract_vars(body: str) -> list[str]:
    """Return variables in first-appearance order (not alphabetical)."""
    seen, out = set(), []
    for name in VAR_PATTERN.findall(body):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def serialize(p: dict) -> dict:
    p = dict(p)
    p["tags"] = json.loads(p.get("tags") or "[]")
    p["favorite"] = bool(p.get("favorite"))
    p["variables"] = extract_vars(p["body"])
    return p


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional auth: enforced only when PROMPTFORGE_REQUIRE_KEY=1."""
    if not config.REQUIRE_API_KEY:
        return
    if not x_api_key or not db.touch_api_key(x_api_key):
        raise HTTPException(401, "invalid or missing X-API-Key")


# -------------------------------- health --------------------------------

@app.get("/api/health", tags=["system"])
def health():
    provider = db.get_active_provider()
    return {
        "status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION,
        "llm_ready": bool(provider and provider.get("api_key")),
        "provider": (provider or {}).get("name"),
    }


@app.get("/api/stats/overview", tags=["system"])
def overview():
    a = db.analytics()
    return {
        "prompts": a["total_prompts"], "runs": a["total_runs"], "favorites": a["favorites"],
        "avg_score": a["avg_score"], "avg_latency_ms": a["avg_latency_ms"], "total_tokens": a["total_tokens"],
    }


# -------------------------------- prompts -------------------------------

@app.get("/api/prompts", tags=["prompts"])
def list_prompts(q: str = "", category: str = "", tag: str = "", favorites: bool = False):
    return [serialize(p) for p in db.list_prompts(q, category, tag, favorites)]


@app.get("/api/categories", tags=["prompts"])
def categories():
    return sorted({p["category"] for p in db.list_prompts() if p["category"]})


@app.post("/api/prompts", status_code=201, tags=["prompts"], dependencies=[Depends(require_api_key)])
def create_prompt(inp: PromptIn):
    return serialize(db.create_prompt(inp.model_dump()))


@app.get("/api/prompts/{pid}", tags=["prompts"])
def get_prompt(pid: str):
    p = db.get_prompt(pid)
    if not p:
        raise HTTPException(404, "prompt not found")
    return serialize(p)


@app.patch("/api/prompts/{pid}", tags=["prompts"], dependencies=[Depends(require_api_key)])
def update_prompt(pid: str, inp: PromptPatch):
    p = db.update_prompt(pid, {k: v for k, v in inp.model_dump().items() if v is not None})
    if not p:
        raise HTTPException(404, "prompt not found")
    return serialize(p)


@app.delete("/api/prompts/{pid}", tags=["prompts"], dependencies=[Depends(require_api_key)])
def delete_prompt(pid: str):
    if not db.delete_prompt(pid):
        raise HTTPException(404, "prompt not found")
    return {"deleted": True}


@app.post("/api/prompts/{pid}/favorite", tags=["prompts"])
def toggle_favorite(pid: str):
    p = db.get_prompt(pid)
    if not p:
        raise HTTPException(404, "prompt not found")
    return serialize(db.update_prompt(pid, {"favorite": not bool(p["favorite"])}))


# -------------------------------- versions ------------------------------

@app.get("/api/prompts/{pid}/versions", tags=["versions"])
def versions(pid: str):
    return db.list_versions(pid)


@app.post("/api/prompts/{pid}/versions/{version}/restore", tags=["versions"])
def restore(pid: str, version: int):
    p = db.restore_version(pid, version)
    if not p:
        raise HTTPException(404, "version not found")
    return serialize(p)


@app.get("/api/prompts/{pid}/versions/{version}/diff", tags=["versions"])
def diff_version(pid: str, version: int):
    import difflib
    versions_list = db.list_versions(pid)
    target = next((v for v in versions_list if v["version"] == version), None)
    current = db.get_prompt(pid)
    if not target or not current:
        raise HTTPException(404, "not found")
    prev = next((v for v in versions_list if v["version"] == version - 1), None)
    old = prev["body"].splitlines(keepends=True) if prev else []
    new = target["body"].splitlines(keepends=True)
    return {"diff": "".join(difflib.unified_diff(old, new, f"v{version-1}", f"v{version}", lineterm="\n"))}


# --------------------------------- runs ---------------------------------

@app.post("/api/prompts/{pid}/run", tags=["runs"], dependencies=[Depends(require_api_key)])
def run_prompt(pid: str, inp: RunIn):
    p = db.get_prompt(pid)
    if not p:
        raise HTTPException(404, "prompt not found")
    body = inp.prompt_body or p["body"]
    rendered = render(body, inp.variables)
    if not inp.call_llm:
        rid = db.add_run({"prompt_id": pid, "rendered": rendered, "variables": inp.variables})["id"]
        return {"id": rid, "rendered": rendered, "output": "", "mocked": False}

    provider = db.get_active_provider()
    if not provider:
        raise HTTPException(400, "no provider configured — add one in Settings")
    try:
        c = llm.chat(
            base_url=provider["base_url"], api_key=provider["api_key"],
            model=inp.model or provider["model"], prompt=rendered,
            temperature=inp.temperature if inp.temperature is not None else provider["temperature"],
            max_tokens=inp.max_tokens or provider["max_tokens"],
        )
    except llm.LLMError as e:
        db.add_run({"prompt_id": pid, "rendered": rendered, "variables": inp.variables,
                    "status": f"error: {e.message}", "model": provider["model"]})
        raise HTTPException(502, str(e))

    rid = db.add_run({
        "prompt_id": pid, "rendered": rendered, "variables": inp.variables,
        "model": c.model, "output": c.text, "latency_ms": c.latency_ms,
        "tokens_in": c.tokens_in, "tokens_out": c.tokens_out,
    })["id"]
    return {"id": rid, "rendered": rendered, "output": c.text, "model": c.model,
            "latency_ms": c.latency_ms, "tokens_in": c.tokens_in,
            "tokens_out": c.tokens_out, "mocked": c.mocked}


@app.post("/api/prompts/{pid}/stream", tags=["runs"])
def stream_prompt(pid: str, inp: RunIn):
    """Server-Sent Events stream for the playground."""
    p = db.get_prompt(pid)
    if not p:
        raise HTTPException(404, "prompt not found")
    provider = db.get_active_provider()
    if not provider:
        raise HTTPException(400, "no provider configured")
    rendered = render(inp.prompt_body or p["body"], inp.variables)

    def gen():
        yield f"data: {json.dumps({'event': 'start', 'prompt': rendered})}\n\n"
        try:
            for delta in llm.chat_stream(
                base_url=provider["base_url"], api_key=provider["api_key"],
                model=inp.model or provider["model"], prompt=rendered,
                temperature=inp.temperature if inp.temperature is not None else provider["temperature"],
                max_tokens=inp.max_tokens or provider["max_tokens"],
            ):
                yield f"data: {json.dumps({'event': 'delta', 'text': delta})}\n\n"
            yield f"data: {json.dumps({'event': 'done'})}\n\n"
        except llm.LLMError as e:
            yield f"data: {json.dumps({'event': 'error', 'message': e.message})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/prompts/{pid}/compare", tags=["runs"])
def compare(pid: str, inp: CompareIn):
    """Run two prompt variants back to back (A/B)."""
    provider = db.get_active_provider()
    if not provider:
        raise HTTPException(400, "no provider configured")
    group = db._uid()
    results = []
    for variant, body in (("A", inp.body_a), ("B", inp.body_b)):
        rendered = render(body, inp.variables)
        try:
            c = llm.chat(base_url=provider["base_url"], api_key=provider["api_key"],
                         model=inp.model or provider["model"], prompt=rendered,
                         temperature=provider["temperature"], max_tokens=provider["max_tokens"])
            rid = db.add_run({"prompt_id": pid, "rendered": rendered, "variables": inp.variables,
                              "model": c.model, "output": c.text, "latency_ms": c.latency_ms,
                              "tokens_in": c.tokens_in, "tokens_out": c.tokens_out,
                              "variant": variant, "group_id": group})["id"]
            results.append({"variant": variant, "id": rid, "rendered": rendered, "output": c.text,
                            "latency_ms": c.latency_ms, "tokens_out": c.tokens_out})
        except llm.LLMError as e:
            results.append({"variant": variant, "rendered": rendered, "error": e.message})
    return {"group_id": group, "results": results}


@app.get("/api/prompts/{pid}/runs", tags=["runs"])
def prompt_runs(pid: str, limit: int = Query(30, le=200)):
    return db.list_runs(pid, limit)


@app.get("/api/runs", tags=["runs"])
def all_runs(limit: int = Query(50, le=200)):
    return db.list_runs("", limit)


@app.post("/api/runs/{rid}/score", tags=["runs"])
def score(rid: str, inp: ScoreIn):
    if not db.score_run(rid, inp.score, inp.feedback):
        raise HTTPException(404, "run not found")
    return {"ok": True}


# ------------------------------- analytics ------------------------------

@app.get("/api/analytics", tags=["analytics"])
def get_analytics():
    return db.analytics()


# ------------------------------- providers ------------------------------

@app.get("/api/providers", tags=["providers"])
def providers():
    return db.list_providers()


@app.post("/api/providers", tags=["providers"])
def upsert_provider(inp: ProviderIn):
    data = {k: v for k, v in inp.model_dump().items() if v is not None}
    return db.upsert_provider(data)


@app.post("/api/providers/{pid}/activate", tags=["providers"])
def activate(pid: str):
    if not db.activate_provider(pid):
        raise HTTPException(404, "provider not found")
    return {"ok": True}


@app.delete("/api/providers/{pid}", tags=["providers"])
def delete_provider(pid: str):
    if not db.delete_provider(pid):
        raise HTTPException(404, "provider not found")
    return {"deleted": True}


@app.post("/api/providers/{pid}/ping", tags=["providers"])
def ping_provider(pid: str):
    p = next((x for x in db.list_providers() if x["id"] == pid), None)
    if not p:
        raise HTTPException(404, "provider not found")
    raw = db.get_active_provider()
    try:
        row = db.get_db().execute("SELECT * FROM providers WHERE id=?", (pid,)).fetchone()
        c = llm.chat(row["base_url"], row["api_key"], row["model"], "Reply with exactly: pong", max_tokens=8)
        return {"ok": True, "latency_ms": c.latency_ms, "mocked": c.mocked, "reply": c.text.strip()[:40]}
    except llm.LLMError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=502)
    finally:
        del raw


# -------------------------------- api keys ------------------------------

@app.get("/api/api-keys", tags=["api-keys"])
def api_keys():
    return db.list_api_keys()


@app.post("/api/api-keys", status_code=201, tags=["api-keys"])
def create_api_key(inp: ApiKeyIn):
    return db.create_api_key(inp.label)


@app.delete("/api/api-keys/{key}", tags=["api-keys"])
def delete_api_key(key: str):
    if not db.delete_api_key(key):
        raise HTTPException(404, "key not found")
    return {"deleted": True}


# ------------------------------ import/export ---------------------------

@app.get("/api/export", tags=["io"])
def export_all():
    payload = {"version": config.APP_VERSION, "prompts": [serialize(p) for p in db.list_prompts()]}
    return JSONResponse(payload, headers={"Content-Disposition": 'attachment; filename="promptforge-export.json"'})


@app.post("/api/import", tags=["io"])
def import_all(inp: ImportIn):
    n = db.import_prompts(inp.prompts)
    return {"imported": n}


# --------------------------------- SPA ----------------------------------

static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="spa")
