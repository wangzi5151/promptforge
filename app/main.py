"""PromptForge - open-source prompt engineering workbench.

FastAPI application serving both a REST API and the built-in SPA frontend.
"""
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, config, db

app = FastAPI(
    title="PromptForge API",
    version=__version__,
    description="Open-source prompt engineering workbench — manage, version, test and ship prompts.",
)

VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@app.on_event("startup")
def startup() -> None:
    db.init_db()


# ---------- models ----------

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


class ApiKeyIn(BaseModel):
    label: str = ""


# ---------- helpers ----------

def render(body: str, variables: dict) -> str:
    def sub(m):
        return str(variables.get(m.group(1), m.group(0)))
    return VAR_PATTERN.sub(sub, body)


def extract_vars(body: str) -> list[str]:
    return sorted(set(VAR_PATTERN.findall(body)))


def serialize(p: dict) -> dict:
    p = dict(p)
    p["tags"] = __import__("json").loads(p.get("tags") or "[]")
    p["variables"] = extract_vars(p["body"])
    return p


# ---------- API ----------

@app.get("/api/health")
def health():
    return {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION}


@app.get("/api/prompts")
def list_prompts(q: str = "", category: str = "", tag: str = "", favorites: bool = False):
    return [serialize(p) for p in db.list_prompts(q, category, tag, favorites)]


@app.post("/api/prompts", status_code=201)
def create_prompt(inp: PromptIn):
    return serialize(db.create_prompt(inp.model_dump()))


@app.get("/api/prompts/{pid}")
def get_prompt(pid: str):
    p = db.get_prompt(pid)
    if not p:
        raise HTTPException(404, "prompt not found")
    return serialize(p)


@app.patch("/api/prompts/{pid}")
def update_prompt(pid: str, inp: PromptPatch):
    p = db.update_prompt(pid, {k: v for k, v in inp.model_dump().items() if v is not None})
    if not p:
        raise HTTPException(404, "prompt not found")
    return serialize(p)


@app.delete("/api/prompts/{pid}")
def delete_prompt(pid: str):
    if not db.delete_prompt(pid):
        raise HTTPException(404, "prompt not found")
    return {"deleted": True}


@app.get("/api/prompts/{pid}/versions")
def versions(pid: str):
    return db.list_versions(pid)


@app.post("/api/prompts/{pid}/run")
def run_prompt(pid: str, inp: RunIn):
    p = db.get_prompt(pid)
    if not p:
        raise HTTPException(404, "prompt not found")
    body = inp.prompt_body or p["body"]
    rendered = render(body, inp.variables)
    db.add_run(pid, rendered, inp.variables)
    return {"rendered": rendered}


@app.get("/api/analytics")
def get_analytics():
    return db.analytics()


@app.get("/api/api-keys")
def get_api_keys():
    return db.list_api_keys()


@app.post("/api/api-keys", status_code=201)
def create_api_key(inp: ApiKeyIn):
    return db.create_api_key(inp.label)


@app.delete("/api/api-keys/{key}")
def delete_api_key(key: str):
    if not db.delete_api_key(key):
        raise HTTPException(404, "key not found")
    return {"deleted": True}


@app.get("/api/export")
def export_all():
    return JSONResponse({"prompts": [serialize(p) for p in db.list_prompts()]}, headers={
        "Content-Disposition": "attachment; filename=promptforge-export.json"})


# ---------- SPA ----------

static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="spa")
