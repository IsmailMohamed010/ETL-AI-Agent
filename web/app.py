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
import zipfile
import tempfile
import atexit
import logging
import io
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


@app.route("/")
@app.route("/index.html")
def home():
    return send_from_directory(BASE_DIR, "index.html")

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
JOBS_FILE     = os.path.join(BASE_DIR, "jobs.json")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Sub-agent directories (relative to BASE_DIR)
DIR_DB_EXTRACT     = os.path.join(BASE_DIR, "extract_agent", "db")
DIR_SCRAPE         = os.path.join(BASE_DIR, "..", "Extract Agent", "web scraper")
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
    now = datetime.utcnow().isoformat()
    job = {
        "id":             job_id,
        "user_id":        request.current_user["id"],
        "sources":        sources,
        "description":    desc,
        "payloads":       {s: data.get(s, {}) for s in sources},
        "status":         "pending",
        "progress":       0,
        "error":          None,
        "results":        None,
        "created_at":     now,
        "updated_at":     now,
        "message":        "Job created, waiting to start…",
        "uploaded_files": [],
    }
    jobs[job_id] = job
    save_jobs()

    thread = threading.Thread(target=run_pipeline, args=(job_id,), daemon=True)
    thread.start()

    return jsonify({
        "jobId": job_id,
        "status": job["status"],
        "message": job["message"],
        "createdAt": job["created_at"],
        "progress": 0
    }), 201


@app.route("/api/jobs/<job_id>/upload", methods=["POST"])
@require_auth
def upload_file(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["user_id"] != request.current_user["id"]:
        return jsonify({"error": "Forbidden."}), 403

    ALLOWED_EXT = {'.csv', '.xlsx', '.xls', '.json', '.txt', '.pdf'}
    MAX_SIZE = 50 * 1024 * 1024
    
    saved = []
    for key in request.files:
        f = request.files[key]
        
        if not f.filename:
            return jsonify({"error": "Filename is empty"}), 400
        
        file_ext = os.path.splitext(f.filename)[1].lower()
        if file_ext not in ALLOWED_EXT:
            return jsonify({
                "error": f"File type '{file_ext}' not allowed. Allowed: {', '.join(sorted(ALLOWED_EXT))}"
            }), 400
        
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        f.seek(0)
        
        if file_size > MAX_SIZE:
            return jsonify({
                "error": f"File too large ({file_size/1024/1024:.1f}MB). Max size: 50MB"
            }), 413
        
        filename = f"{job_id}_{uuid.uuid4().hex[:6]}_{f.filename}"
        path = os.path.join(UPLOAD_FOLDER, filename)
        f.save(path)
        saved.append(path)

    job["uploaded_files"].extend(saved)
    job["updated_at"] = datetime.utcnow().isoformat()
    save_jobs()
    return jsonify({
        "uploaded": saved,
        "count": len(saved),
        "totalSize": sum(os.path.getsize(p) for p in saved)
    }), 200


@app.route("/api/jobs/<job_id>/status", methods=["GET"])
@require_auth
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["user_id"] != request.current_user["id"]:
        return jsonify({"error": "Forbidden."}), 403
    
    return jsonify({
        "jobId": job_id,
        "status": job["status"],
        "message": job.get("message", ""),
        "progress": job.get("progress", 0),
        "error": job.get("error"),
        "results": job.get("results"),
        "createdAt": job.get("created_at"),
        "updatedAt": job.get("updated_at")
    })


@app.route("/api/jobs/<job_id>/download", methods=["GET"])
@require_auth
def download_job_results(job_id):
    """Download job results as ZIP file."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["user_id"] != request.current_user["id"]:
        return jsonify({"error": "Forbidden."}), 403
    
    if job["status"] not in ["done", "completed"]:
        return jsonify({
            "error": f"Job not completed. Current status: {job['status']}"
        }), 400
    
    try:
        import io
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add uploaded files if they still exist
            for file_path in job.get("uploaded_files", []):
                if os.path.exists(file_path):
                    arc_name = os.path.basename(file_path)
                    zip_file.write(file_path, arcname=arc_name)
            
            # Add job results if available
            if job.get("results"):
                results_data = json.dumps(job["results"], indent=2)
                zip_file.writestr("results.json", results_data)
            
            # Add job metadata
            metadata = {
                "jobId": job_id,
                "status": job["status"],
                "message": job.get("message", ""),
                "progress": job.get("progress", 100),
                "createdAt": job.get("created_at"),
                "completedAt": job.get("updated_at"),
                "description": job.get("description", "")
            }
            metadata_data = json.dumps(metadata, indent=2)
            zip_file.writestr("metadata.json", metadata_data)
        
        zip_buffer.seek(0)
        
        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"job-{job_id}-results.zip"
        )
    
    except Exception as e:
        print(f"[{job_id}] Download error: {e}")
        return jsonify({"error": f"Failed to generate results: {str(e)}"}), 500


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
@require_auth
def cancel_job(job_id):
    """Cancel a pending or processing job."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["user_id"] != request.current_user["id"]:
        return jsonify({"error": "Forbidden."}), 403
    
    if job["status"] not in ["pending", "processing"]:
        return jsonify({
            "error": f"Cannot cancel job with status '{job['status']}'. Can only cancel pending/processing jobs."
        }), 400
    
    job["status"] = "cancelled"
    job["message"] = "Job cancelled by user"
    job["updated_at"] = datetime.utcnow().isoformat()
    save_jobs()
    
    print(f"[{job_id}] Job cancelled by user {request.current_user['id']}")
    
    return jsonify({
        "jobId": job_id,
        "status": "cancelled",
        "message": "Job cancelled successfully"
    }), 200


# ── CHAT ENDPOINT ──────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@require_auth
def chat():
    data     = request.get_json() or {}
    job_id   = data.get("jobId")
    messages = data.get("messages", [])

    if not job_id:
        return jsonify({"error": "jobId required"}), 400
    if not messages or not isinstance(messages, list):
        return jsonify({"error": "messages must be array"}), 400

    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found."}), 404
    if job["user_id"] != request.current_user["id"]:
        return jsonify({"error": "Forbidden."}), 403
    if job["status"] != "done":
        return jsonify({"error": f"Job not complete. Status: {job['status']}"}), 400

    try:
        import sys
        sys.path.insert(0, DIR_RAG)
        from web.main import chat as rag_chat
        reply = rag_chat(job_id, messages)
    except ImportError:
        last_user = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        reply = f"[Placeholder] You: {last_user}"
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({
        "content": reply,
        "jobId": job_id,
        "timestamp": datetime.utcnow().isoformat(),
        "role": "assistant"
    }), 200


# ── PIPELINE WORKER ────────────────────────────────────────────────────────────
def run_pipeline(job_id: str):
    """
    Full ETL pipeline:
      1. Extract  (all selected sources, sequentially)
      2. Transform
      3. Load
    """
    job = jobs[job_id]

    def update(status: str, message: str, progress: int = None, error: str = None):
        job["status"]  = status
        job["message"] = message
        job["updated_at"] = datetime.utcnow().isoformat()
        if progress is not None:
            job["progress"] = progress
        if error is not None:
            job["error"] = error
        save_jobs()
        
        if error:
            logger.error(f"[{job_id}] {status.upper()} — {message} | ERROR: {error}")
        else:
            logger.info(f"[{job_id}] {status.upper()} — {message} (progress: {job.get('progress', 0)}%)")

    try:
        sources  = job["sources"]
        payloads = job["payloads"]
        desc     = job["description"]
        
        logger.info(f"[{job_id}] Starting pipeline with sources: {sources}")

        # ── STAGE 1: EXTRACT (each selected source) ────────────────────────
        update("processing", "Starting extraction phase…", progress=10)
        logger.info(f"[{job_id}] Extract started")
        
        for i, source in enumerate(sources):
            progress_val = 10 + (i * 20 // max(len(sources), 1))
            update("processing", f"Extracting from source: {source}…", progress=progress_val)
            logger.info(f"[{job_id}] Extracting from {source}")

            if source == "db":
                _run_db_extraction(job, payloads["db"], desc)

            elif source == "scrape":
                _run_scrape_extraction(job, payloads["scrape"], desc)

            elif source == "files":
                _run_file_extraction(job, payloads["files"], desc)

        logger.info(f"[{job_id}] Extract completed")

        # ── STAGE 2: TRANSFORM ─────────────────────────────────────────────
        update("processing", "Running transformation layer…", progress=50)
        logger.info(f"[{job_id}] Transform started")
        
        _run_subprocess(
            ["python", "transformation_engine.py"],
            cwd=DIR_TRANSFORM,
            job_id=job_id,
            step="transform",
        )
        
        logger.info(f"[{job_id}] Transform completed")

        # ── STAGE 3: LOAD ──────────────────────────────────────────────────
        update("processing", "Loading results…", progress=75)
        logger.info(f"[{job_id}] Load started")
        
        _run_subprocess(
            ["python", "load.py"],
            cwd=DIR_LOAD,
            job_id=job_id,
            step="load",
        )
        
        logger.info(f"[{job_id}] Load completed")

        # Mark as done
        update("done", "Pipeline complete.", progress=100)
        logger.info(f"[{job_id}] Pipeline SUCCESS - all stages completed")

    except ImportError as e:
        logger.warning(f"[{job_id}] ImportError: {e} — running simulation.")
        update("processing", "Agents unavailable, running simulation…", progress=20)
        _simulate_pipeline(job_id)

    except RuntimeError as e:
        error_msg = str(e)
        logger.error(f"[{job_id}] RuntimeError during pipeline: {error_msg}")
        update("error", f"Pipeline failed: {error_msg}", error=error_msg)

    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logger.exception(f"[{job_id}] {error_msg}")
        update("error", error_msg, error=str(e))


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
        logger.warning(f"[{job_id}][{step}] Directory not found: {cwd} — skipping (simulation mode).")
        time.sleep(2)
        return

    logger.info(f"[{job_id}][{step}] Executing: {' '.join(cmd)} in {cwd}")
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
            logger.debug(f"[{job_id}][{step}] STDOUT: {result.stdout[-800:]}")
        if result.stderr:
            logger.warning(f"[{job_id}][{step}] STDERR: {result.stderr[-400:]}")

        if result.returncode != 0:
            error_msg = result.stderr[-300:] if result.stderr else "Unknown error"
            logger.error(f"[{job_id}][{step}] Failed with exit code {result.returncode}")
            raise RuntimeError(
                f"Step '{step}' failed (exit {result.returncode}): {error_msg}"
            )
        
        logger.info(f"[{job_id}][{step}] Completed successfully")

    except subprocess.TimeoutExpired:
        logger.error(f"[{job_id}][{step}] Timeout after 10 minutes")
        raise RuntimeError(f"Step '{step}' timed out after 10 minutes.")
    except FileNotFoundError:
        # python not in PATH or script missing — simulation fallback
        logger.warning(f"[{job_id}][{step}] Script not found — simulating.")
        time.sleep(2)


# ── SIMULATION FALLBACK ────────────────────────────────────────────────────────

def _simulate_pipeline(job_id: str):
    """Simulate pipeline execution when agents are unavailable."""
    logger.info(f"[{job_id}] Running simulation (agents unavailable)")
    
    steps = [
        (3, "processing", "Connecting to source(s)…", 15),
        (3, "processing", "Extracting data…", 40),
        (3, "processing", "Running transformation layer…", 70),
        (3, "processing", "Loading results…", 90),
        (1, "done",       "Pipeline complete.", 100),
    ]
    
    for delay, status, msg, progress in steps:
        time.sleep(delay)
        jobs[job_id]["status"]  = status
        jobs[job_id]["message"] = msg
        jobs[job_id]["progress"] = progress
        jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        save_jobs()
        logger.info(f"[{job_id}] [{status.upper()}] {msg} ({progress}%)")


# ── RUN ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("DataAgent API v2 (multi-source) starting…")
    logger.info(f"Jobs file: {JOBS_FILE}")
    logger.info(f"Upload folder: {UPLOAD_FOLDER}")
    logger.info(f"Active jobs: {len(jobs)}")
    logger.info("=" * 80)
    
    app.run(debug=True, port=5000)