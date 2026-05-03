"""
DataAgent — Flask Backend API  (v2 — multi-source)
===================================================

Pipeline commands (real):
  DB extraction  : python Extract.py --run "<sql>" --source-tables "<tables>"
  Web scraping   : python main.py --url "<url>" --query "<query>"   (file_scraping/main.py)
  File extraction: python main.py                                    (file_extract/main.py)
  Transform      : python transformation_engine.py
  Load           : python load.py
  RAG            : python main.py                                    (rag_chatbot/main.py)

Multi-source job payload (POST /api/jobs):
{
  "sources": ["db", "scrape", "files"],       // one or more
  "description": "...",
  "db":     { "endpoints": [...], "hints": [...] },
  "scrape": { "urls": [...], "hints": [...] },
  "files":  { "count": N, "descriptions": [...] }
}
"""

import os
import uuid
import json
import subprocess
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE     = os.path.join(BASE_DIR, "jobs.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Sub-agent directories (relative to BASE_DIR)
DIR_DB_EXTRACT     = os.path.join(BASE_DIR, "extract_agent", "db")
DIR_SCRAPE         = os.path.join(BASE_DIR, "extract_agent", "file_scraping")
DIR_FILE_EXTRACT   = os.path.join(BASE_DIR, "extract_agent", "file_extract")
DIR_TRANSFORM      = os.path.join(BASE_DIR, "transformation_layer")
DIR_LOAD           = os.path.join(BASE_DIR, "load_agent")
DIR_RAG            = os.path.join(BASE_DIR, "rag_chatbot")

# ── JOB STORE ─────────────────────────────────────────────────────────────────
jobs: dict = {}
if os.path.exists(JOBS_FILE):
    with open(JOBS_FILE) as f:
        jobs = json.load(f)

# ── USER STORE (replace with real DB + hashed passwords in production) ────────
users:  dict = {
    "demo@dataagent.ai": {"id": "u0", "name": "Demo User", "password": "demo1234"}
}
tokens: dict = {}   # token → user_id


def save_jobs():
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2)


# ── AUTH HELPERS ──────────────────────────────────────────────────────────────
def get_user_from_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    user_id = tokens.get(token)
    if not user_id:
        return None
    for email, u in users.items():
        if u["id"] == user_id:
            return {**u, "email": email}
    return None


def require_auth(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_user_from_token()
        if not user:
            return jsonify({"error": "Unauthorized"}), 401
        request.current_user = user
        return fn(*args, **kwargs)
    return wrapper


# ── AUTH ENDPOINTS ────────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json() or {}
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    user = users.get(email)
    if not user or user["password"] != password:
        return jsonify({"error": "Invalid email or password."}), 401
    token = str(uuid.uuid4())
    tokens[token] = user["id"]
    return jsonify({"token": token, "user": {"id": user["id"], "name": user["name"], "email": email}})


@app.route("/api/auth/register", methods=["POST"])
def register():
    data     = request.get_json() or {}
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    if email in users:
        return jsonify({"error": "An account with this email already exists."}), 409
    user_id = str(uuid.uuid4())
    users[email] = {"id": user_id, "name": name, "password": password}
    token = str(uuid.uuid4())
    tokens[token] = user_id
    return jsonify({"token": token, "user": {"id": user_id, "name": name, "email": email}}), 201


@app.route("/api/me", methods=["GET"])
@require_auth
def me():
    u = request.current_user
    return jsonify({"user": {"id": u["id"], "name": u["name"], "email": u["email"]}})


# ── JOB ENDPOINTS ─────────────────────────────────────────────────────────────
@app.route("/api/jobs", methods=["POST"])
@require_auth
def create_job():
    """
    Accepts multi-source payload:
    {
      "sources":     ["db", "scrape", "files"],   // 1+ sources
      "description": "...",
      "db":          { "endpoints": [...], "hints": [...] },
      "scrape":      { "urls": [...], "hints": [...] },
      "files":       { "count": N, "descriptions": [...] }
    }
    """
    data    = request.get_json() or {}
    sources = data.get("sources", [])
    desc    = data.get("description", "").strip()

    VALID_SOURCES = {"db", "scrape", "files"}

    # ── Validation ─────────────────────────────────────────────────────────
    if not sources or not isinstance(sources, list):
        return jsonify({"error": "sources must be a non-empty list."}), 400

    invalid = [s for s in sources if s not in VALID_SOURCES]
    if invalid:
        return jsonify({"error": f"Invalid source(s): {invalid}. Must be one of {list(VALID_SOURCES)}."}), 400

    if len(desc) < 20:
        return jsonify({"error": "description must be at least 20 characters."}), 400

    # ── Validate each source payload ──────────────────────────────────────
    if "db" in sources:
        db_payload = data.get("db", {})
        endpoints  = db_payload.get("endpoints", [])
        if not endpoints or not all(e.strip() for e in endpoints):
            return jsonify({"error": "db.endpoints must have at least one non-empty connection string."}), 400

    if "scrape" in sources:
        sc_payload = data.get("scrape", {})
        urls       = sc_payload.get("urls", [])
        if not urls or not all(u.strip() for u in urls):
            return jsonify({"error": "scrape.urls must have at least one non-empty URL."}), 400

    if "files" in sources:
        fi_payload = data.get("files", {})
        count      = fi_payload.get("count", 0)
        if not count or count < 1:
            return jsonify({"error": "files.count must be at least 1."}), 400

    # ── Create job ────────────────────────────────────────────────────────
    job_id = "job-" + str(uuid.uuid4())[:8].upper()
    job = {
        "id":             job_id,
        "user_id":        request.current_user["id"],
        "sources":        sources,
        "description":    desc,
        "payloads":       {s: data.get(s, {}) for s in sources},
        "status":         "pending",
        "created_at":     datetime.utcnow().isoformat(),
        "message":        "Job created, waiting to start…",
        "uploaded_files": [],
    }
    jobs[job_id] = job
    save_jobs()

    thread = threading.Thread(target=run_pipeline, args=(job_id,), daemon=True)
    thread.start()

    return jsonify({"jobId": job_id}), 201


@app.route("/api/jobs/<job_id>/upload", methods=["POST"])
@require_auth
def upload_file(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["user_id"] != request.current_user["id"]:
        return jsonify({"error": "Forbidden."}), 403

    saved = []
    for key in request.files:
        f        = request.files[key]
        filename = f"{job_id}_{uuid.uuid4().hex[:6]}_{f.filename}"
        path     = os.path.join(UPLOAD_FOLDER, filename)
        f.save(path)
        saved.append(path)

    job["uploaded_files"].extend(saved)
    save_jobs()
    return jsonify({"uploaded": saved})


@app.route("/api/jobs/<job_id>/status", methods=["GET"])
@require_auth
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["user_id"] != request.current_user["id"]:
        return jsonify({"error": "Forbidden."}), 403
    return jsonify({"status": job["status"], "message": job.get("message", "")})


# ── CHAT ENDPOINT ──────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@require_auth
def chat():
    data     = request.get_json() or {}
    job_id   = data.get("jobId")
    messages = data.get("messages", [])

    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["status"] != "done":
        return jsonify({"error": "Job is not completed yet."}), 400

    try:
        import sys
        sys.path.insert(0, DIR_RAG)
        from main import chat as rag_chat  # type: ignore
        reply = rag_chat(job_id, messages)
    except ImportError:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        reply = (
            f"[RAG Chatbot placeholder] You asked: \"{last_user}\". "
            f"Job `{job_id}` completed. Connect `rag_chatbot/main.py` to enable real answers."
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"content": reply})


# ── PIPELINE WORKER ────────────────────────────────────────────────────────────
def run_pipeline(job_id: str):
    """
    Full ETL pipeline:
      1. Extract  (all selected sources, sequentially)
      2. Transform
      3. Load
    """
    job = jobs[job_id]

    def update(status: str, message: str):
        job["status"]  = status
        job["message"] = message
        save_jobs()
        print(f"[{job_id}] {status.upper()} — {message}")

    try:
        sources  = job["sources"]
        payloads = job["payloads"]
        desc     = job["description"]

        # ── STAGE 1: EXTRACT (each selected source) ────────────────────────
        for source in sources:
            update("pending", f"Extracting from source: {source}…")

            if source == "db":
                _run_db_extraction(job, payloads["db"], desc)

            elif source == "scrape":
                _run_scrape_extraction(job, payloads["scrape"], desc)

            elif source == "files":
                _run_file_extraction(job, payloads["files"], desc)

        # ── STAGE 2: TRANSFORM ─────────────────────────────────────────────
        update("pending", "Running transformation layer…")
        _run_subprocess(
            ["python", "transformation_engine.py"],
            cwd=DIR_TRANSFORM,
            job_id=job_id,
            step="transform",
        )

        # ── STAGE 3: LOAD ──────────────────────────────────────────────────
        update("pending", "Loading results…")
        _run_subprocess(
            ["python", "load.py"],
            cwd=DIR_LOAD,
            job_id=job_id,
            step="load",
        )

        update("done", "Pipeline complete.")

    except ImportError as e:
        print(f"[{job_id}] ImportError: {e} — running simulation.")
        _simulate_pipeline(job_id)

    except RuntimeError as e:
        update("error", str(e))

    except Exception as e:
        update("error", f"Unexpected error: {e}")


# ── SOURCE RUNNERS ─────────────────────────────────────────────────────────────

def _run_db_extraction(job: dict, payload: dict, desc: str):
    """
    Calls:  python Extract.py --run "<sql>" --source-tables "<tables>"
    One subprocess per endpoint.
    """
    endpoints = payload.get("endpoints", [])
    hints     = payload.get("hints", [])
    job_id    = job["id"]

    for i, endpoint in enumerate(endpoints):
        hint = hints[i] if i < len(hints) else ""
        sql  = hint if hint else "SELECT * FROM information_schema.tables LIMIT 100"

        _run_subprocess(
            ["python", "Extract.py", "--run", sql, "--source-tables", endpoint],
            cwd=DIR_DB_EXTRACT,
            job_id=job_id,
            step=f"db-{i+1}",
        )


def _run_scrape_extraction(job: dict, payload: dict, desc: str):
    """
    Calls:  python main.py --url "<url>" --query "<query>"
    One subprocess per URL (non-interactive via CLI args).
    """
    urls   = payload.get("urls", [])
    hints  = payload.get("hints", [])
    job_id = job["id"]

    for i, url in enumerate(urls):
        query = hints[i] if i < len(hints) and hints[i] else desc

        _run_subprocess(
            ["python", "main.py", "--url", url, "--query", query],
            cwd=DIR_SCRAPE,
            job_id=job_id,
            step=f"scrape-{i+1}",
        )


def _run_file_extraction(job: dict, payload: dict, desc: str):
    """
    Calls:  python main.py
    File paths are passed via env var FILE_PATHS (comma-separated).
    The file_extract/main.py should read os.environ.get("FILE_PATHS").
    """
    file_paths = job.get("uploaded_files", [])
    job_id     = job["id"]

    env = os.environ.copy()
    env["FILE_PATHS"] = ",".join(file_paths)
    env["JOB_DESC"]   = desc

    _run_subprocess(
        ["python", "main.py"],
        cwd=DIR_FILE_EXTRACT,
        job_id=job_id,
        step="files",
        extra_env=env,
    )


# ── SUBPROCESS HELPER ──────────────────────────────────────────────────────────

def _run_subprocess(
    cmd: list,
    cwd: str,
    job_id: str,
    step: str,
    extra_env: dict | None = None,
):
    """
    Run a command in a subprocess. Raises RuntimeError on failure.
    Falls back gracefully if the target directory doesn't exist yet.
    """
    if not os.path.isdir(cwd):
        print(f"[{job_id}][{step}] Directory not found: {cwd} — skipping (simulation mode).")
        time.sleep(2)
        return

    print(f"[{job_id}][{step}] Running: {' '.join(cmd)} (cwd={cwd})")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=600,          # 10-minute safety timeout
            env=extra_env or os.environ.copy(),
        )
        if result.stdout:
            print(f"[{job_id}][{step}] STDOUT: {result.stdout[-800:]}")
        if result.stderr:
            print(f"[{job_id}][{step}] STDERR: {result.stderr[-400:]}")

        if result.returncode != 0:
            raise RuntimeError(
                f"Step '{step}' failed (exit {result.returncode}): {result.stderr[-300:]}"
            )

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Step '{step}' timed out after 10 minutes.")
    except FileNotFoundError:
        # python not in PATH or script missing — simulation fallback
        print(f"[{job_id}][{step}] Script not found — simulating.")
        time.sleep(2)


# ── SIMULATION FALLBACK ────────────────────────────────────────────────────────

def _simulate_pipeline(job_id: str):
    steps = [
        (3, "pending", "Connecting to source(s)…"),
        (3, "pending", "Extracting data…"),
        (3, "pending", "Running transformation layer…"),
        (3, "pending", "Loading results…"),
        (1, "done",    "Pipeline complete."),
    ]
    for delay, status, msg in steps:
        time.sleep(delay)
        jobs[job_id]["status"]  = status
        jobs[job_id]["message"] = msg
        save_jobs()


# ── RUN ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("DataAgent API v2 (multi-source) running on http://localhost:5000")
    app.run(debug=True, port=5000)