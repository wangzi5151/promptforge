"""PromptForge data layer v2.

SQLite + WAL, thread-local connections, forward-only migrations.
"""
import json
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
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
    return conn


def _now() -> float:
    return time.time()


def _uid() -> str:
    return uuid.uuid4().hex


# Each migration runs once; version tracked in schema_meta.
MIGRATIONS: list[tuple[int, str]] = [
    (1, """
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
        created_at REAL
    );
    CREATE TABLE IF NOT EXISTS api_keys (
        key TEXT PRIMARY KEY,
        label TEXT DEFAULT '',
        created_at REAL,
        last_used REAL
    );
    """),
    (2, """
    ALTER TABLE runs ADD COLUMN model TEXT DEFAULT '';
    ALTER TABLE runs ADD COLUMN output TEXT DEFAULT '';
    ALTER TABLE runs ADD COLUMN latency_ms INTEGER DEFAULT 0;
    ALTER TABLE runs ADD COLUMN tokens_in INTEGER DEFAULT 0;
    ALTER TABLE runs ADD COLUMN tokens_out INTEGER DEFAULT 0;
    ALTER TABLE runs ADD COLUMN score INTEGER DEFAULT 0;
    ALTER TABLE runs ADD COLUMN feedback TEXT DEFAULT '';
    ALTER TABLE runs ADD COLUMN variant TEXT DEFAULT 'A';
    ALTER TABLE runs ADD COLUMN group_id TEXT DEFAULT '';
    ALTER TABLE runs ADD COLUMN status TEXT DEFAULT 'ok';
    CREATE TABLE IF NOT EXISTS providers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        base_url TEXT NOT NULL,
        api_key TEXT DEFAULT '',
        model TEXT NOT NULL,
        temperature REAL DEFAULT 0.7,
        max_tokens INTEGER DEFAULT 1024,
        is_active INTEGER DEFAULT 1,
        created_at REAL
    );
    """),
    (3, """
    CREATE INDEX IF NOT EXISTS idx_prompts_updated ON prompts(updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_prompts_cat ON prompts(category);
    CREATE INDEX IF NOT EXISTS idx_runs_prompt ON runs(prompt_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_runs_group ON runs(group_id);
    CREATE INDEX IF NOT EXISTS idx_versions_prompt ON prompt_versions(prompt_id, version DESC);
    """),
]


def init_db(seed: bool = True) -> None:
    db = get_db()
    db.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INTEGER PRIMARY KEY, applied_at REAL)")
    cur = db.execute("SELECT COALESCE(MAX(version),0) v FROM schema_meta").fetchone()["v"]
    for ver, sql in MIGRATIONS:
        if ver <= cur:
            continue
        db.executescript(sql)
        db.execute("INSERT INTO schema_meta (version, applied_at) VALUES (?,?)", (ver, _now()))
        db.commit()
    if seed:
        seed_demo_data()
    if not db.execute("SELECT COUNT(*) c FROM providers").fetchone()["c"]:
        seed_providers()


# ------------------------------- seeding -------------------------------

TEMPLATES = [
    ("Senior Code Reviewer", "engineering", ["code", "review", "security"],
     "逐条定位 bug、安全漏洞与风格问题的资深代码评审助手",
     "You are a senior {{language}} engineer performing a rigorous code review.\n\n"
     "## Code under review\n```{{language}}\n{{code}}\n```\n\n"
     "## Review focus\n{{focus}}\n\n"
     "## Output format\n"
     "Return findings grouped by severity (BLOCKER / MAJOR / MINOR), each with:\n"
     "- line reference\n- what is wrong and why it matters\n- a concrete fix (diff or snippet)\n\n"
     "End with a one-paragraph verdict and an overall risk score from 1-10.", "gpt-4o"),
    ("SQL Query Optimizer", "engineering", ["sql", "database", "performance"],
     "把慢查询改写成高效等价 SQL，并解释执行计划",
     "You are a database performance expert.\n\n"
     "## Slow query\n```sql\n{{sql}}\n```\n\n"
     "## Schema context\n{{schema}}\n\n"
     "## Constraints\n{{constraints}}\n\n"
     "Produce:\n1. Rewritten query\n2. What was slow and why (index usage, cardinality, join order)\n"
     "3. Recommended indexes with exact DDL\n4. Expected improvement and how to verify it", "any"),
    ("RAG Chunking Strategist", "engineering", ["rag", "llm", "retrieval"],
     "为特定文档类型设计检索召回最优的分块策略",
     "Design a chunking strategy for {{doc_type}} documents (avg length {{avg_length}}, "
     "structure: {{structure}}).\n\n"
     "Deliver:\n- chunk size and overlap with justification\n- boundary rules (semantic vs fixed)\n"
     "- metadata to attach per chunk\n- a failure-mode table and mitigations\n"
     "- an evaluation plan (recall@k, answer faithfulness)", "any"),
    ("Product Naming Wizard", "marketing", ["naming", "branding"],
     "生成可注册、可传播的产品名并给出理由",
     "Brainstorm {{count}} product names for: {{product}}.\n"
     "Audience: {{audience}}. Tone: {{tone}}.\n\n"
     "For each name give: the name, why it works, a risk check (trademark / pronunciation / "
     "negative connotation in major markets), and a sample tagline. Sort best-first.", "any"),
    ("Cold Email Composer", "marketing", ["email", "sales", "outreach"],
     "高回复率的冷启动邮件，含主题行与 A/B 变体",
     "Write a cold email to {{role}} at {{company}}.\n"
     "Our value prop: {{value}}\n\n"
     "Requirements: subject line under 50 chars, body under 120 words, one clear CTA, "
     "no hype words. Then give 2 alternative subject lines and explain which will win and why.", "any"),
    ("Meeting Summarizer", "productivity", ["meeting", "summary", "actions"],
     "把会议记录转成决策、行动项与未决问题",
     "Summarize the transcript below.\n\n## Transcript\n{{transcript}}\n\n"
     "Output exactly these sections:\n"
     "### Decisions\n### Action items (owner + due date)\n### Open questions\n### Risks\n\n"
     "Be ruthless about brevity — no filler, no restating the transcript.", "any"),
    ("Customer Support Triage", "support", ["support", "triage", "classification"],
     "自动分类工单并起草符合品牌语调的回复",
     "Classify this support ticket into one of: bug / billing / feature_request / abuse / other.\n\n"
     "Ticket:\n{{ticket}}\n\n"
     "Return JSON: {\"category\": ..., \"severity\": 1-5, \"confidence\": 0-1, \"reason\": \"...\"}\n"
     "Then draft a reply in a {{tone}} tone that acknowledges, explains next steps, and sets "
     "an expectation. Never promise timelines we cannot keep.", "any"),
    ("YouTube Hook Writer", "content", ["video", "script", "hooks"],
     "15 秒内抓住观众的三种开场钩子",
     "Write 3 hook options (first 15 seconds) for a video about {{topic}}.\n"
     "Audience: {{audience}}. Platform: {{platform}}.\n\n"
     "Each hook must create an open loop in the first sentence. Label the psychological "
     "lever used (curiosity gap / stakes / contrarian claim). Then pick the strongest and say why.", "any"),
    ("Structured Extraction Agent", "engineering", ["json", "extraction", "parsing"],
     "从非结构化文本中稳定抽取结构化字段",
     "Extract the following fields from the text: {{fields}}\n\n## Text\n{{text}}\n\n"
     "Rules:\n- Output valid JSON only, no prose, no code fences\n"
     "- Use null when a field is absent; never invent values\n"
     "- If a value is ambiguous, pick the most literal reading\n\n"
     "Return: {\"data\": {...}, \"confidence\": 0-1, \"notes\": \"...\"}", "any"),
    ("Error Message Humanizer", "productivity", ["ux", "errors", "writing"],
     "把技术报错翻译成用户能懂、知道怎么办的提示",
     "Rewrite this technical error into a user-facing message.\n\n## Raw error\n{{error}}\n\n"
     "Context: {{context}}\n\n"
     "Deliver:\n- headline (≤60 chars, no jargon)\n- one-sentence explanation of what happened\n"
     "- the single next action the user should take\n- a 'technical details' line for support", "any"),
]

PROVIDERS = [
    ("OpenAI", "https://api.openai.com/v1", "gpt-4o-mini"),
    ("DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat"),
    ("Ollama (local)", "http://localhost:11434/v1", "llama3.1"),
]


def seed_demo_data() -> None:
    db = get_db()
    if db.execute("SELECT COUNT(*) c FROM prompts").fetchone()["c"]:
        return
    now = _now()
    for i, (title, cat, tags, desc, body, hint) in enumerate(TEMPLATES):
        pid = _uid()
        created = now - (len(TEMPLATES) - i) * 7200
        db.execute(
            "INSERT INTO prompts (id,title,body,category,tags,description,model_hint,favorite,version,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,1,?,?)",
            (pid, title, body, cat, json.dumps(tags), desc, hint, 1 if i < 3 else 0, created, created),
        )
        db.execute("INSERT INTO prompt_versions (id,prompt_id,version,body,note,created_at) VALUES (?,?,1,?,?,?)",
                   (_uid(), pid, body, "initial version", created))
    db.commit()


def seed_providers() -> None:
    db = get_db()
    for i, (name, base, model) in enumerate(PROVIDERS):
        db.execute("INSERT INTO providers (id,name,base_url,api_key,model,temperature,max_tokens,is_active,created_at)"
                   " VALUES (?,?,?,'',?,0.7,1024,?,?)",
                   (_uid(), name, base, model, 1 if i == 0 else 0, _now() - i))
    db.commit()


# ------------------------------- prompts -------------------------------

def list_prompts(q: str = "", category: str = "", tag: str = "", favorites: bool = False) -> list[dict]:
    sql = "SELECT * FROM prompts WHERE 1=1"
    args: list = []
    if q:
        sql += " AND (title LIKE ? OR body LIKE ? OR description LIKE ?)"
        args += [f"%{q}%"] * 3
    if category:
        sql += " AND category = ?"
        args.append(category)
    if tag:
        sql += " AND tags LIKE ?"
        args.append(f'%"{tag}"%')
    if favorites:
        sql += " AND favorite = 1"
    sql += " ORDER BY favorite DESC, updated_at DESC"
    return [dict(r) for r in get_db().execute(sql, args).fetchall()]


def get_prompt(pid: str) -> dict | None:
    row = get_db().execute("SELECT * FROM prompts WHERE id=?", (pid,)).fetchone()
    return dict(row) if row else None


def create_prompt(data: dict) -> dict:
    pid, now = _uid(), _now()
    db = get_db()
    db.execute(
        "INSERT INTO prompts (id,title,body,category,tags,description,model_hint,favorite,version,created_at,updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,1,?,?)",
        (pid, data["title"], data["body"], data.get("category") or "general",
         json.dumps(data.get("tags") or []), data.get("description") or "",
         data.get("model_hint") or "", int(bool(data.get("favorite"))), now, now),
    )
    db.execute("INSERT INTO prompt_versions (id,prompt_id,version,body,note,created_at) VALUES (?,?,1,?,?,?)",
               (_uid(), pid, data["body"], "created", now))
    db.commit()
    return get_prompt(pid)


def update_prompt(pid: str, data: dict) -> dict | None:
    p = get_prompt(pid)
    if not p:
        return None
    db, now = get_db(), _now()
    fields, args = [], []
    for k in ("title", "body", "category", "description", "model_hint"):
        if data.get(k) is not None:
            fields.append(f"{k}=?")
            args.append(data[k])
    if data.get("tags") is not None:
        fields.append("tags=?")
        args.append(json.dumps(data["tags"]))
    if data.get("favorite") is not None:
        fields.append("favorite=?")
        args.append(int(bool(data["favorite"])))

    body = data.get("body")
    if body and body != p["body"]:
        new_ver = p["version"] + 1
        fields.append("version=?")
        args.append(new_ver)
        db.execute("INSERT INTO prompt_versions (id,prompt_id,version,body,note,created_at) VALUES (?,?,?,?,?,?)",
                   (_uid(), pid, new_ver, body, data.get("change_note") or "", now))
    if not fields:
        return p
    fields.append("updated_at=?")
    args += [now, pid]
    db.execute(f"UPDATE prompts SET {', '.join(fields)} WHERE id=?", args)
    db.commit()
    return get_prompt(pid)


def delete_prompt(pid: str) -> bool:
    db = get_db()
    cur = db.execute("DELETE FROM prompts WHERE id=?", (pid,))
    db.execute("DELETE FROM prompt_versions WHERE prompt_id=?", (pid,))
    db.execute("DELETE FROM runs WHERE prompt_id=?", (pid,))
    db.commit()
    return cur.rowcount > 0


def list_versions(pid: str) -> list[dict]:
    rows = get_db().execute(
        "SELECT id,version,note,body,created_at FROM prompt_versions WHERE prompt_id=? ORDER BY version DESC",
        (pid,)).fetchall()
    return [dict(r) for r in rows]


def restore_version(pid: str, version: int) -> dict | None:
    row = get_db().execute("SELECT body FROM prompt_versions WHERE prompt_id=? AND version=?", (pid, version)).fetchone()
    if not row:
        return None
    return update_prompt(pid, {"body": row["body"], "change_note": f"restored from v{version}"})


# -------------------------------- runs --------------------------------

def add_run(data: dict) -> dict:
    rid = _uid()
    get_db().execute(
        "INSERT INTO runs (id,prompt_id,rendered,variables,created_at,model,output,latency_ms,"
        "tokens_in,tokens_out,variant,group_id,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (rid, data.get("prompt_id", ""), data.get("rendered", ""), json.dumps(data.get("variables") or {}),
         _now(), data.get("model", ""), data.get("output", ""), data.get("latency_ms", 0),
         data.get("tokens_in", 0), data.get("tokens_out", 0), data.get("variant", "A"),
         data.get("group_id", ""), data.get("status", "ok")),
    )
    get_db().commit()
    return {"id": rid}


def score_run(rid: str, score: int, feedback: str = "") -> bool:
    cur = get_db().execute("UPDATE runs SET score=?, feedback=? WHERE id=?", (score, feedback, rid))
    get_db().commit()
    return cur.rowcount > 0


def list_runs(pid: str = "", limit: int = 50) -> list[dict]:
    if pid:
        rows = get_db().execute(
            "SELECT * FROM runs WHERE prompt_id=? ORDER BY created_at DESC LIMIT ?", (pid, limit)).fetchall()
    else:
        rows = get_db().execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["variables"] = json.loads(d.get("variables") or "{}")
        out.append(d)
    return out


# ------------------------------ analytics ------------------------------

def analytics() -> dict:
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM prompts").fetchone()["c"]
    runs_total = db.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
    favs = db.execute("SELECT COUNT(*) c FROM prompts WHERE favorite=1").fetchone()["c"]
    scored = db.execute("SELECT AVG(score) a, COUNT(*) c FROM runs WHERE score>0").fetchone()
    avg_latency = db.execute("SELECT AVG(latency_ms) a FROM runs WHERE latency_ms>0").fetchone()["a"] or 0
    total_tokens = db.execute("SELECT SUM(tokens_in+tokens_out) s FROM runs").fetchone()["s"] or 0

    by_cat = {r["category"]: r["c"] for r in
              db.execute("SELECT category, COUNT(*) c FROM prompts GROUP BY category ORDER BY c DESC")}

    # 14-day trend, zero-filled
    since = _now() - 14 * 86400
    buckets: dict[str, int] = {}
    for r in db.execute("SELECT created_at FROM runs WHERE created_at>=?", (since,)):
        day = time.strftime("%m-%d", time.localtime(r["created_at"]))
        buckets[day] = buckets.get(day, 0) + 1

    top = [dict(r) for r in db.execute(
        "SELECT p.id, p.title, p.category, COUNT(r.id) runs, ROUND(AVG(NULLIF(r.score,0)),2) avg_score "
        "FROM prompts p LEFT JOIN runs r ON r.prompt_id=p.id GROUP BY p.id "
        "ORDER BY runs DESC, p.updated_at DESC LIMIT 6")]

    return {
        "total_prompts": total,
        "total_runs": runs_total,
        "favorites": favs,
        "avg_score": round(scored["a"] or 0, 2),
        "scored_runs": scored["c"],
        "avg_latency_ms": round(avg_latency),
        "total_tokens": total_tokens,
        "by_category": by_cat,
        "trend": buckets,
        "top_prompts": top,
    }


# ------------------------------ providers ------------------------------

def list_providers() -> list[dict]:
    rows = get_db().execute("SELECT * FROM providers ORDER BY created_at").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["has_key"] = bool(d.pop("api_key", ""))
        out.append(d)
    return out


def get_active_provider() -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM providers WHERE is_active=1 AND api_key!='' LIMIT 1").fetchone()
    if row:
        return dict(row)
    row = db.execute("SELECT * FROM providers WHERE is_active=1 LIMIT 1").fetchone()
    return dict(row) if row else None


def upsert_provider(data: dict) -> dict:
    db = get_db()
    pid = data.get("id")
    if pid:
        fields, args = [], []
        for k in ("name", "base_url", "api_key", "model", "temperature", "max_tokens", "is_active"):
            if data.get(k) is not None:
                fields.append(f"{k}=?")
                args.append(data[k])
        if fields:
            args.append(pid)
            db.execute(f"UPDATE providers SET {', '.join(fields)} WHERE id=?", args)
    else:
        pid = _uid()
        db.execute("INSERT INTO providers (id,name,base_url,api_key,model,temperature,max_tokens,is_active,created_at)"
                   " VALUES (?,?,?,?,?,?,?,?,?)",
                   (pid, data.get("name") or "Custom", data.get("base_url") or "", data.get("api_key") or "",
                    data.get("model") or "", data.get("temperature", 0.7), data.get("max_tokens", 1024),
                    int(bool(data.get("is_active", True))), _now()))
    db.commit()
    row = db.execute("SELECT * FROM providers WHERE id=?", (pid,)).fetchone()
    d = dict(row)
    d["has_key"] = bool(d.pop("api_key", ""))
    return d


def activate_provider(pid: str) -> bool:
    db = get_db()
    if not db.execute("SELECT 1 FROM providers WHERE id=?", (pid,)).fetchone():
        return False
    db.execute("UPDATE providers SET is_active=0")
    db.execute("UPDATE providers SET is_active=1 WHERE id=?", (pid,))
    db.commit()
    return True


def delete_provider(pid: str) -> bool:
    cur = get_db().execute("DELETE FROM providers WHERE id=?", (pid,))
    get_db().commit()
    return cur.rowcount > 0


# ------------------------------ api keys ------------------------------

def list_api_keys() -> list[dict]:
    rows = get_db().execute("SELECT key,label,created_at,last_used FROM api_keys ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def create_api_key(label: str) -> dict:
    key = "pf_" + uuid.uuid4().hex[:28]
    get_db().execute("INSERT INTO api_keys (key,label,created_at) VALUES (?,?,?)", (key, label, _now()))
    get_db().commit()
    return {"key": key, "label": label}


def delete_api_key(key: str) -> bool:
    cur = get_db().execute("DELETE FROM api_keys WHERE key=?", (key,))
    get_db().commit()
    return cur.rowcount > 0


def touch_api_key(key: str) -> bool:
    cur = get_db().execute("UPDATE api_keys SET last_used=? WHERE key=?", (_now(), key))
    get_db().commit()
    return cur.rowcount > 0


# ------------------------------- import -------------------------------

def import_prompts(items: list[dict]) -> int:
    n = 0
    for it in items:
        if not it.get("title") or not it.get("body"):
            continue
        create_prompt({
            "title": str(it["title"])[:120], "body": str(it["body"]),
            "category": it.get("category") or "general",
            "tags": it.get("tags") or [], "description": it.get("description") or "",
            "model_hint": it.get("model_hint") or "",
        })
        n += 1
    return n
