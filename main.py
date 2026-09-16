import os
import sys
import uuid
import time
import json
import shutil
import zipfile
import subprocess
import threading
import re
import socket
import secrets
import hashlib
from pathlib import Path
from typing import Dict, Optional, List
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure local bin/ffmpeg and spotdl's ffmpeg are in PATH
BASE_DIR = Path(__file__).resolve().parent
local_bin = BASE_DIR / "bin"
local_ffmpeg = BASE_DIR / "ffmpeg"
spotdl_dir = Path.home() / ".spotdl"

for extra_path in [local_bin, local_ffmpeg, spotdl_dir]:
    if extra_path.exists():
        os.environ["PATH"] = str(extra_path) + os.pathsep + os.environ.get("PATH", "")

# --- Configuration ---
MAX_CONCURRENT_DOWNLOADS = 3
SUBPROCESS_TIMEOUT_SECONDS = None  # No timeout — let downloads run to completion
TASK_EXPIRY_SECONDS = 86400  # 24 hours
CLEANUP_INTERVAL_SECONDS = 600  # 10 minutes
RATE_LIMIT_MAX_REQUESTS = 15
RATE_LIMIT_WINDOW_SECONDS = 60

ALLOWED_FORMATS = {"mp3", "flac", "m4a", "opus", "ogg", "wav"}

# --- Password & Authentication ---
PASSWORD_FILE = BASE_DIR / "password.txt"
SECRET_SALT = secrets.token_hex(16)

def get_app_password() -> str:
    """Retrieve app password from environment variable or password.txt file."""
    env_pw = os.environ.get("APP_PASSWORD")
    if env_pw is not None:
        return env_pw.strip()
    if PASSWORD_FILE.exists():
        try:
            return PASSWORD_FILE.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    # Default initial password if none exists
    default_pw = "spotifetch"
    try:
        PASSWORD_FILE.write_text(default_pw, encoding="utf-8")
    except Exception:
        pass
    return default_pw

def generate_auth_token(password: str) -> str:
    """Deterministic token generated from password + server salt."""
    return hashlib.sha256(f"{password}:{SECRET_SALT}".encode()).hexdigest()

def is_authenticated(request: Request) -> bool:
    current_pw = get_app_password()
    if not current_pw:
        return True  # No password required if empty

    expected_token = generate_auth_token(current_pw)

    # 1. Check Cookie
    cookie_token = request.cookies.get("spotifetch_auth")
    if cookie_token and secrets.compare_digest(cookie_token, expected_token):
        return True

    # 2. Check Authorization Header (Bearer token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        header_token = auth_header.split(" ", 1)[1].strip()
        if secrets.compare_digest(header_token, expected_token):
            return True

    # 3. Check X-Auth-Token Header
    x_token = request.headers.get("X-Auth-Token", "")
    if x_token and secrets.compare_digest(x_token, expected_token):
        return True

    return False

def require_auth(request: Request):
    """Raise 401 if user is not authenticated."""
    if not is_authenticated(request):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please enter the site password."
        )

app = FastAPI(title="SpotiFetch API", version="1.3.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOADS_DIR = BASE_DIR / "downloads"
STATIC_DIR = BASE_DIR / "static"

DOWNLOADS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# --- Strict Spotify URL validation ---
SPOTIFY_URL_PATTERN = re.compile(
    r'^https?://open\.spotify\.com/(intl-[a-zA-Z0-9_-]+/)?(track|album|playlist|artist|episode|show)/[a-zA-Z0-9]+/?$'
)
SPOTIFY_URI_PATTERN = re.compile(
    r'^spotify:(track|album|playlist|artist|episode|show):[a-zA-Z0-9]+$'
)

# --- UUID validation ---
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

def is_valid_task_id(task_id: str) -> bool:
    """Validate that task_id is a proper UUID to prevent path traversal."""
    return bool(UUID_PATTERN.match(task_id))

def is_valid_spotify_url(url: str) -> bool:
    """Strictly validate Spotify URLs to prevent SSRF."""
    return bool(SPOTIFY_URL_PATTERN.match(url) or SPOTIFY_URI_PATTERN.match(url))

# --- Rate limiter ---
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        with self.lock:
            timestamps = self.requests[client_ip]
            self.requests[client_ip] = [
                t for t in timestamps if now - t < self.window_seconds
            ]
            if len(self.requests[client_ip]) >= self.max_requests:
                return False
            self.requests[client_ip].append(now)
            return True

rate_limiter = RateLimiter(RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)

# --- Models ---
class LoginRequest(BaseModel):
    password: str

class PreviewRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format: Optional[str] = "mp3"
    selected_urls: Optional[List[str]] = None

# --- Download Task ---
class DownloadTask:
    def __init__(
        self,
        task_id: str,
        url: str,
        item_type: str,
        audio_format: str = "mp3",
        selected_urls: Optional[List[str]] = None
    ):
        self.task_id = task_id
        self.url = url
        self.item_type = item_type
        self.audio_format = audio_format if audio_format in ALLOWED_FORMATS else "mp3"
        self.selected_urls = selected_urls or []
        self.status = "queued"  # queued, downloading, zipping, ready, failed
        self.progress_msg = "Task queued..."
        self.logs: List[str] = []
        self.file_path: Optional[str] = None
        self.filename: Optional[str] = None
        self.file_size: int = 0
        self.item_count: int = 0
        self.error: Optional[str] = None
        self.created_at: float = time.time()
        self.completed_at: Optional[float] = None

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "url": self.url,
            "item_type": self.item_type,
            "audio_format": self.audio_format,
            "selected_count": len(self.selected_urls) if self.selected_urls else None,
            "status": self.status,
            "progress_msg": self.progress_msg,
            "logs": self.logs[-30:],  # Return latest 30 log lines
            "filename": self.filename,
            "file_size": self.file_size,
            "item_count": self.item_count,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

tasks: Dict[str, DownloadTask] = {}
tasks_lock = threading.Lock()

def clean_spotify_url(url: str) -> str:
    url = url.strip()
    if "?" in url:
        url = url.split("?")[0]
    return url

def detect_spotify_type(url: str) -> str:
    url_lower = url.lower()
    if "track" in url_lower:
        return "Single Track"
    elif "album" in url_lower:
        return "Album"
    elif "playlist" in url_lower:
        return "Playlist"
    elif "artist" in url_lower:
        return "Artist Discography"
    elif "episode" in url_lower or "show" in url_lower:
        return "Podcast / Episode"
    return "Spotify Media"

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()

def sanitize_error_for_client(error: str) -> str:
    error = re.sub(r'[A-Za-z]:\\[^\s"\']+', '[server-path]', error)
    error = re.sub(r'/home/[^\s"\']+', '[server-path]', error)
    if len(error) > 500:
        error = error[:500] + "..."
    return error

def run_spotdl_sync(task: DownloadTask):
    task_dir = DOWNLOADS_DIR / task.task_id
    task_dir.mkdir(exist_ok=True)
    task.status = "downloading"
    clean_url = clean_spotify_url(task.url)

    if task.selected_urls:
        task.progress_msg = f"Downloading {len(task.selected_urls)} selected songs ({task.audio_format.upper()})..."
    elif "artist" in clean_url.lower():
        task.progress_msg = "Fetching entire artist discography metadata. Please wait..."
    else:
        task.progress_msg = f"Connecting to Spotify & searching audio sources ({task.audio_format.upper()})..."

    process = None
    try:
        output_template = "{title} - {artist}.{output-ext}"
        
        if task.selected_urls:
            download_targets = task.selected_urls
        else:
            download_targets = [clean_url]

        cmd = [
            sys.executable,
            "-m",
            "spotdl",
            "download",
            *download_targets,
            "--output",
            output_template,
            "--format",
            task.audio_format,
            "--audio",
            "youtube",
            "soundcloud",
            "youtube-music",
            "--overwrite",
            "skip",
            "--dont-filter-results",
            "--bitrate",
            "auto",
            "--threads",
            "8",
            "--preload",
            "--simple-tui",
            "--print-errors"
        ]

        target_desc = f"{len(task.selected_urls)} selected tracks" if task.selected_urls else clean_url
        task.logs.append(f"Starting download ({task.audio_format.upper()}) for: {target_desc}")

        env = os.environ.copy()
        for extra_path in [local_bin, local_ffmpeg, spotdl_dir]:
            if extra_path.exists():
                env["PATH"] = str(extra_path) + os.pathsep + env.get("PATH", "")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(task_dir),
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env
        )

        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            stripped_line = line.strip()
            if stripped_line:
                task.logs.append(stripped_line)
                if len(task.logs) > 150:
                    task.logs = task.logs[-150:]

                # Parse progress clues
                if "Processing query" in stripped_line or "Found" in stripped_line:
                    task.progress_msg = stripped_line
                elif "Downloading" in stripped_line:
                    task.progress_msg = stripped_line
                elif "Converting" in stripped_line or "Embedding" in stripped_line:
                    task.progress_msg = stripped_line
                elif "Downloaded" in stripped_line:
                    task.progress_msg = stripped_line

        # Wait for SpotDL to complete
        if SUBPROCESS_TIMEOUT_SECONDS:
            try:
                process.wait(timeout=SUBPROCESS_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                task.status = "failed"
                task.error = "Download timed out."
                task.progress_msg = "Download timed out."
                task.logs.append("Process killed: exceeded timeout.")
                return
        else:
            process.wait()

        # Find all downloaded audio files recursively
        audio_extensions = {".mp3", ".m4a", ".flac", ".opus", ".ogg", ".wav", ".aac", ".webm"}
        audio_files = [
            p for p in task_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in audio_extensions and not p.name.endswith(".zip")
        ]

        if not audio_files:
            error_details = "\n".join(task.logs[-5:]) if task.logs else "No audio stream found"
            task.status = "failed"
            task.error = sanitize_error_for_client(
                f"No files were downloaded. SpotDL output: {error_details}"
            )
            task.progress_msg = "Download failed."
            return

        task.item_count = len(audio_files)

        if len(audio_files) == 1:
            single_file = audio_files[0]
            task.file_path = str(single_file)
            task.filename = single_file.name
            task.file_size = single_file.stat().st_size
            task.status = "ready"
            task.progress_msg = f"Ready: {task.filename}"
            task.completed_at = time.time()
        else:
            task.status = "zipping"
            task.progress_msg = f"Packaging {len(audio_files)} songs into a ZIP archive..."

            type_name = sanitize_filename(task.item_type)
            zip_name = f"{type_name}_{task.task_id[:8]}.zip"
            zip_path = task_dir / zip_name

            # ZIP_STORED: fast packaging with zero CPU wasted on audio re-compression
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zip_f:
                for file in audio_files:
                    zip_f.write(file, arcname=file.name)

            task.file_path = str(zip_path)
            task.filename = zip_name
            task.file_size = zip_path.stat().st_size
            task.status = "ready"
            task.progress_msg = f"Ready! {len(audio_files)} songs archived."
            task.completed_at = time.time()

    except Exception as e:
        task.status = "failed"
        task.error = sanitize_error_for_client(str(e))
        task.progress_msg = "Error occurred during download."
        task.logs.append(f"Exception: {str(e)}")
    finally:
        if process and process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=5)
            except Exception:
                pass

# Bounded thread pool for concurrent downloads
download_pool = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS, thread_name_prefix="spotdl")

def start_task_thread(task: DownloadTask):
    download_pool.submit(run_spotdl_sync, task)

# Periodically clean up old task files (older than 24 hours)
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            expired_ids = []
            with tasks_lock:
                for task_id, task in list(tasks.items()):
                    if now - task.created_at > TASK_EXPIRY_SECONDS:
                        expired_ids.append(task_id)

            for task_id in expired_ids:
                task_dir = DOWNLOADS_DIR / task_id
                if task_dir.exists():
                    shutil.rmtree(task_dir, ignore_errors=True)
                with tasks_lock:
                    tasks.pop(task_id, None)

            # Prune old directories on disk
            for entry in DOWNLOADS_DIR.iterdir():
                if entry.is_dir():
                    try:
                        if now - entry.stat().st_mtime > TASK_EXPIRY_SECONDS:
                            shutil.rmtree(entry, ignore_errors=True)
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(CLEANUP_INTERVAL_SECONDS)

cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For for proxied setups."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

# --- Authentication Endpoints ---
@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check if password authentication is required and if the current client is authenticated."""
    current_pw = get_app_password()
    return {
        "auth_required": bool(current_pw),
        "authenticated": is_authenticated(request)
    }

@app.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    """Authenticate with site password and receive auth token & session cookie."""
    current_pw = get_app_password()
    if not current_pw:
        return JSONResponse(content={"status": "success", "message": "No password required"})

    if not secrets.compare_digest(req.password.strip(), current_pw):
        raise HTTPException(
            status_code=401,
            detail="Incorrect password. Please try again."
        )

    token = generate_auth_token(current_pw)
    response = JSONResponse(content={
        "status": "success",
        "token": token,
        "message": "Authenticated successfully"
    })

    # Set persistent cookie for 30 days
    response.set_cookie(
        key="spotifetch_auth",
        value=token,
        max_age=2592000,
        httponly=False,
        samesite="lax",
        path="/"
    )
    return response

@app.post("/api/auth/logout")
async def auth_logout():
    """Clear authentication session cookie."""
    response = JSONResponse(content={"status": "success", "message": "Logged out successfully"})
    response.delete_cookie(key="spotifetch_auth", path="/")
    return response

# --- Core App Endpoints (Protected) ---
@app.post("/api/preview")
async def preview_tracks(req: PreviewRequest, request: Request):
    """Fetch tracklist metadata for Spotify URL so the user can select individual songs."""
    require_auth(request)

    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again."
        )

    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    cleaned_url = clean_spotify_url(url)
    if not is_valid_spotify_url(cleaned_url):
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid Spotify link (e.g., https://open.spotify.com/album/...)"
        )

    item_type = detect_spotify_type(cleaned_url)

    try:
        env = os.environ.copy()
        for extra_path in [local_bin, local_ffmpeg, spotdl_dir]:
            if extra_path.exists():
                env["PATH"] = str(extra_path) + os.pathsep + env.get("PATH", "")

        proc = subprocess.run(
            [sys.executable, "-m", "spotdl", "save", cleaned_url, "--save-file", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=env
        )

        stdout_text = proc.stdout or ""
        json_start = stdout_text.find("[")
        json_end = stdout_text.rfind("]")

        if json_start == -1 or json_end == -1 or json_end <= json_start:
            raise ValueError("Could not retrieve tracklist metadata from Spotify.")

        raw_json = stdout_text[json_start:json_end + 1]
        songs_data = json.loads(raw_json)

        parsed_songs = []
        for idx, s in enumerate(songs_data):
            duration_sec = s.get("duration", 0) or 0
            mins = int(duration_sec) // 60
            secs = int(duration_sec) % 60
            duration_str = f"{mins}:{secs:02d}"

            parsed_songs.append({
                "index": idx + 1,
                "name": s.get("name") or "Unknown Title",
                "artist": s.get("artist") or ", ".join(s.get("artists", [])) or "Unknown Artist",
                "album_name": s.get("album_name") or "",
                "duration": duration_str,
                "cover_url": s.get("cover_url") or "",
                "url": s.get("url") or "",
                "song_id": s.get("song_id") or str(idx + 1)
            })

        return {
            "status": "success",
            "item_type": item_type,
            "count": len(parsed_songs),
            "songs": parsed_songs
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Fetching tracklist timed out. Please try again.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tracks: {str(e)}")

@app.post("/api/download")
async def start_download(req: DownloadRequest, request: Request):
    require_auth(request)

    client_ip = get_client_ip(request)
    if not rate_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment before trying again."
        )

    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")

    cleaned_url = clean_spotify_url(url)
    if not is_valid_spotify_url(cleaned_url):
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid Spotify link (e.g., https://open.spotify.com/track/...)"
        )

    # Format check
    audio_format = req.format.lower().strip() if req.format else "mp3"
    if audio_format not in ALLOWED_FORMATS:
        audio_format = "mp3"

    # Selected URLs check
    selected_urls = []
    if req.selected_urls:
        for u in req.selected_urls:
            cu = clean_spotify_url(u)
            if is_valid_spotify_url(cu):
                selected_urls.append(cu)

    # Generate deterministic UUIDv5 for caching/resume
    if selected_urls:
        cache_key = f"{cleaned_url}_{audio_format}_{len(selected_urls)}_{'_'.join(sorted(selected_urls)[:5])}"
    else:
        cache_key = f"{cleaned_url}_{audio_format}"

    task_id = str(uuid.uuid5(uuid.NAMESPACE_URL, cache_key))
    item_type = detect_spotify_type(cleaned_url)
    task = DownloadTask(
        task_id=task_id,
        url=cleaned_url,
        item_type=item_type,
        audio_format=audio_format,
        selected_urls=selected_urls
    )

    with tasks_lock:
        tasks[task_id] = task

    start_task_thread(task)

    return {
        "status": "success",
        "task_id": task_id,
        "item_type": item_type,
        "audio_format": audio_format,
        "selected_count": len(selected_urls) if selected_urls else None,
        "message": "Download task initiated"
    }

@app.get("/api/status/{task_id}")
async def get_status(task_id: str, request: Request):
    require_auth(request)

    if not is_valid_task_id(task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID")
    with tasks_lock:
        task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()

@app.get("/api/file/{task_id}")
async def download_file(task_id: str, request: Request):
    require_auth(request)

    if not is_valid_task_id(task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID")
    with tasks_lock:
        task = tasks.get(task_id)
    if not task or task.status != "ready" or not task.file_path or not os.path.exists(task.file_path):
        raise HTTPException(status_code=404, detail="File is not ready or does not exist")

    resolved_path = Path(task.file_path).resolve()
    if not str(resolved_path).startswith(str(DOWNLOADS_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")

    media_type = "application/zip" if task.filename.endswith(".zip") else "audio/mpeg"
    return FileResponse(
        path=task.file_path,
        filename=task.filename,
        media_type=media_type
    )

@app.get("/api/tasks")
async def list_recent_tasks(request: Request):
    require_auth(request)

    with tasks_lock:
        sorted_tasks = sorted(tasks.values(), key=lambda t: t.created_at, reverse=True)[:10]
        return [t.to_dict() for t in sorted_tasks]

if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

def get_local_ip() -> str:
    """Find the primary local network IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    local_ip = get_local_ip()
    current_password = get_app_password()

    print("\n" + "="*62)
    print(" 🚀 SpotiFetch is running & available on your local network!")
    print("="*62)
    print(f" 💻 Local Computer:       http://localhost:{port}")
    print(f"                         http://127.0.0.1:{port}")
    if local_ip != "127.0.0.1":
        print(f" 📱 Phones/LAN Devices:   http://{local_ip}:{port}")
        print("    (Open this link in the browser of any phone on your Wi-Fi)")
    print("-" * 62)
    print(f" 🔑 Access Password:      {current_password}")
    print("    (To change password, edit password.txt or set APP_PASSWORD)")
    print("="*62 + "\n")
    uvicorn.run("main:app", host=host, port=port, reload=True)
