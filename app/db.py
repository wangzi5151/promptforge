"""PromptForge database layer (SQLite, zero external dependencies)."""
import json
import os
import sqlite3
import threading
import time
import uuid

from . import config

_local = threading.local()


def get_db() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        _local.conn = conn
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS prompts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    tags TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    model_hint TEXT DEFAULT '',
    favorite INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    created_at REAL,
    updated_at REAL
);
CREATE TABLE IF NOT EXISTS prompt_versions (
    id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    body TEXT NOT NULL,
    note TEXT DEFAULT '',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL,
    rendered TEXT NOT NULL,
    variables TEXT DEFAULT '{}',
    score INTEGER DEFAULT 0,
    feedback TEXT DEFAULT '',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS api_keys (
    key TEXT PRIMARY KEY,
    label TEXT DEFAULT '',
    created_at REAL,
    last_used REAL
);
CREATE INDEX IF NOT EXISTS idx_prompts_category ON prompts(category);
CREATE INDEX IF NOT EXISTS idx_runs_prompt ON runs(prompt_id);
"""


def init_db(seed: bool = True) -> None:
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()
    if seed:
        seed_demo_data()


def _now() -> float:
    return time.time()


def seed_demo_data() -> None:
    db = get_db()
    count = db.execute("SELECT COUNT(*) AS c FROM prompts").fetchone()["c"]
    if count:
        return
    demo = [
        ("Code Review Expert", "You are a senior code reviewer.\nReview the following {{language}} code for bugs, security issues, and style:\n\n{{code}}\n\nOutput: a prioritized list of findings with severity labels.", "engineering", ["code", "review", "security"], "Deep, prioritized code review.", "gpt-4o / claude"),
        ("SQL Query Optimizer", "Act as a database expert. Rewrite this SQL to be faster and explain the plan:\n\n{{sql}}\n\nConstraints: {{constraints}}", "engineering", ["sql", "database"], "Rewrites slow SQL with explanations.", "any"),
        ("Product Naming Wizard", "Brainstorm {{count}} product names for: {{product}}.\nAudience: {{audience}}.\nFor each name give a one-line rationale.", "marketing", ["naming", "branding"], "Generates brandable product names.", "any"),
        ("Cold Email Composer", "Write a concise cold email to {{role}} at {{company}}.\nValue prop: {{value}}\nKeep it under 120 words, friendly tone, one clear CTA.", "marketing", ["email", "sales"], "High-converting cold outreach.", "any"),
        ("Meeting Summarizer", "Summarize the meeting transcript below into:\n1. Key decisions\n2. Action items with owners\n3. Open questions\n\nTranscript:\n{{transcript}}", "productivity", ["meeting", "summary"], "Turns transcripts into action.", "any"),
        ("RAG Chunking Strategist", "Design a chunking strategy for documents of type {{doc_type}} with average length {{avg_length}}. Consider overlap, semantic boundaries, and retrieval recall.", "engineering", ["rag", "llm"], "Best-practice RAG chunking plans.", "any"),
        ("Customer Support Triage", "Classify this ticket into (bug / billing / feature / abuse) and draft a reply:\n\n{{ticket}}", "support", ["triage", "support"], "Auto-classify and draft support replies.", "any"),
        ("YouTube Script Hook", "Write 3 hook options (first 15 seconds) for a video about {{topic}} targeting {{audience}}. Make them curiosity-driven.", "content", ["video", "script"], "Scroll-stopping video hooks.", "any"),
    ]
    now = _now()
    for i, (title, body, cat, tags, desc, hint) in enumerate(demo):
        pid = str(uuid.uuid4())
        db.execute(
            "INSERT INTO prompts (id,title,body,category,tags,description,model_hint,favorite,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (pid, title, body, cat, json.dumps(tags), desc, hint, 1 if i in (0, 4) else 0, 1, now - i * 86400, now - i * 3600),
        )
        db.execute(
            "INSERT INTO prompt_versions (id,prompt_id,version,body,note,created_at) VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4()), pid, 1, body, "initial version", now - i * 86400),
        )
    # demo runs for analytics
    import random

    for pid_row in db.execute("SELECT id FROM prompts").fetchall():
        for _ in range(random.randint(3, 12)):
            db.execute(
                "INSERT INTO runs (id,prompt_id,rendered,variables,score,feedback,created_at) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), pid_row["id"], "demo rendered output", "{}", random.randint(3, 5), "", now - random.randint(0, 20) * 86400),
            )
    db.execute("INSERT INTO api_keys (key,label,created_at) VALUES (?,?,?)", ("pf_demo_key_000000", "Demo key", now))
    db.commit()


# ---------------- prompt CRUD ----------------

def list_prompts(q: str = "", category: str = "", tag: str = "", favorites: bool = False):
    sql = "SELECT * FROM prompts WHERE 1=1"
    args = []
    if q:
        sql += " AND (title LIKE ? OR body LIKE ? OR description LIKE ?)"
        args += [f"%{q}%"] * 3
    if category:
        sql += " AND category = ?"
        args.append(category)
    if tag:
        sql += " AND tags LIKE ?"
        args.append(f"%\"{tag}\"%")
    if favorites:
        sql += " AND favorite = 1"
    sql += " ORDER BY favorite DESC, updated_at DESC"
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def get_prompt(pid: str):
    row = get_db().execute("SELECT * FROM prompts WHERE id=?", (pid,)).fetchone()
    return dict(row) if row else None


def create_prompt(data: dict) -> dict:
    pid = str(uuid.uuid4())
    now = _now()
    db = get_db()
    db.execute(
        "INSERT INTO prompts (id,title,body,category,tags,description,model_hint,favorite,version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pid, data["title"], data["body"], data.get("category", "general"), json.dumps(data.get("tags", [])), data.get("description", ""), data.get("model_hint", ""), int(bool(data.get("favorite"))), 1, now, now),
    )
    db.execute("INSERT INTO prompt_versions (id,prompt_id,version,body,note,created_at) VALUES (?,?,?,?,?,?)",
               (str(uuid.uuid4()), pid, 1, data["body"], "created", now))
    db.commit()
    return get_prompt(pid)


def update_prompt(pid: str, data: dict) -> dict | None:
    p = get_prompt(pid)
    if not p:
        return None
    now = _now()
    fields, args = [], []
    for k in ("title", "body", "category", "description", "model_hint"):
        if k in data:
            fields.append(f"{k}=?")
            args.append(data[k])
    if "tags" in data:
        fields.append("tags=?")
        args.append(json.dumps(data["tags"]))
    if "favorite" in data:
        fields.append("favorite=?")
        args.append(int(bool(data["favorite"])))
    new_version = p["version"]
    if data.get("body") and data["body"] != p["body"]:
        new_version = p["version"] + 1
        fields.append("version=?")
        args.append(new_version)
        get_db().execute("INSERT INTO prompt_versions (id,prompt_id,version,body,note,created_at) VALUES (?,?,?,?,?,?)",
                         (str(uuid.uuid4()), pid, new_version, data["body"], data.get("change_note", ""), now))
    if not fields:
        return p
    fields.append("updated_at=?")
    args.append(now)
    args.append(pid)
    get_db().execute(f"UPDATE prompts SET {', '.join(fields)} WHERE id=?", args)
    get_db().commit()
    return get_prompt(pid)


def delete_prompt(pid: str) -> bool:
    db = get_db()
    cur = db.execute("DELETE FROM prompts WHERE id=?", (pid,))
    db.execute("DELETE FROM prompt_versions WHERE prompt_id=?", (pid,))
    db.execute("DELETE FROM runs WHERE prompt_id=?", (pid,))
    db.commit()
    return cur.rowcount > 0


def list_versions(pid: str):
    return [dict(r) for r in get_db().execute(
        "SELECT id,version,note,created_at,body FROM prompt_versions WHERE prompt_id=? ORDER BY version DESC", (pid,)).fetchall()]


# ---------------- runs ----------------

def add_run(pid: str, rendered: str, variables: dict) -> dict:
    rid = str(uuid.uuid4())
    get_db().execute("INSERT INTO runs (id,prompt_id,rendered,variables,created_at) VALUES (?,?,?,?,?)",
                     (rid, pid, rendered, json.dumps(variables), _now()))
    get_db().commit()
    return {"id": rid, "prompt_id": pid, "rendered": rendered}


def analytics() -> dict:
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM prompts").fetchone()["c"]
    runs_total = db.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
    favs = db.execute("SELECT COUNT(*) c FROM prompts WHERE favorite=1").fetchone()["c"]
    by_cat = {r["category"]: r["c"] for r in db.execute("SELECT category, COUNT(*) c FROM prompts GROUP BY category")}
    # runs in last 14 days
    since = _now() - 14 * 86400
    trend = {}
    for r in db.execute("SELECT created_at FROM runs WHERE created_at>=?", (since,)):
        day = time.strftime("%m-%d", time.localtime(r["created_at"]))
        trend[day] = trend.get(day, 0) + 1
    top = [dict(r) for r in db.execute(
        "SELECT p.id, p.title, COUNT(r.id) AS runs FROM prompts p LEFT JOIN runs r ON r.prompt_id=p.id GROUP BY p.id ORDER BY runs DESC LIMIT 5")]
    return {"total_prompts": total, "total_runs": runs_total, "favorites": favs, "by_category": by_cat, "trend": trend, "top_prompts": top}


# ---------------- api keys ----------------

def list_api_keys():
    return [dict(r) for r in get_db().execute("SELECT key,label,created_at,last_used FROM api_keys ORDER BY created_at DESC")]


def create_api_key(label: str) -> dict:
    key = "pf_" + uuid.uuid4().hex[:24]
    get_db().execute("INSERT INTO api_keys (key,label,created_at) VALUES (?,?,?)", (key, label, _now()))
    get_db().commit()
    return {"key": key, "label": label}


def delete_api_key(key: str) -> bool:
    cur = get_db().execute("DELETE FROM api_keys WHERE key=?", (key,))
    get_db().commit()
    return cur.rowcount > 0
