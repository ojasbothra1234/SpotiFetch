# 🎵 SpotiFetch - Spotify Media Downloader WebApp

SpotiFetch is a fast, modern web application designed for downloading Spotify tracks, albums, playlists, podcasts, and **entire singer/artist discographies** with customizable song selection and audio formats.

---

## ✨ Features
- **Singles & Tracks**: Download individual songs directly in high quality with full ID3 metadata and album art.
- **Audio Formats**: Choose your preferred output format: **MP3 (Default)**, M4A, FLAC, OPUS, OGG, or WAV.
- **Custom Song Selection**: Preview tracklists with cover art and durations before downloading, with checkboxes to pick specific songs.
- **Albums & Playlists**: Batch download all or selected tracks packaged automatically into a clean `.zip` archive.
- **Artist Discographies**: Download full discographies (all albums, singles, EPs) with resume and auto-skip support.
- **Real-Time Terminal Output**: Watch live progress and search status directly in the UI.
- **100% Rootless / No Sudo Required**: Runs anywhere in user-space without administrative permissions.

---

## 🐧 Linux / macOS Quick Start (No Sudo Required!)

SpotiFetch can be installed and run **completely without root or sudo permissions**. It automatically configures a local virtual environment and downloads portable versions of FFmpeg and Deno into your user directory.

### Method 1: Automated 1-Click Setup (Recommended)
```bash
chmod +x install_linux.sh start.sh
./install_linux.sh
./start.sh
```

### Method 2: Manual 3-Step Setup (No Root)
```bash
# 1. Create a local virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. (Optional) Let SpotDL download portable FFmpeg & Deno into ~/.spotdl/ if you don't have them
python3 -m spotdl --download-ffmpeg
python3 -m spotdl --download-deno

# 4. Start SpotiFetch
python3 main.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 📱 Android Termux Quick Start (1-Command!)

You can run SpotiFetch directly on your Android phone using **Termux**:

1. Open **Termux** on your phone.
2. Navigate to the `spotify-downloader` folder and run:
   ```bash
   bash termux.sh
   ```
3. It will automatically install `python`, `ffmpeg`, and dependencies, start the server, and **automatically open SpotiFetch in your mobile browser** at `http://localhost:8000`!

---

## 🐳 Docker Deployment (Linux / VPS / NAS)

```bash
docker compose up -d
```
Then open `http://<your-server-ip>:8000`.

---

## 🪟 Windows Quick Start

1. Double-click `start.bat` in the root folder.
2. The server will start and automatically open [http://localhost:8000](http://localhost:8000) in your default browser.

---

## 📁 Project Structure
```
spotify-downloader/
├── main.py              # FastAPI server, SpotDL engine, & async worker pool
├── requirements.txt     # Python dependencies
├── start.sh             # Linux / macOS 1-click launcher (No Sudo)
├── install_linux.sh     # Linux automated installer (No Sudo)
├── start.bat            # Windows 1-click launcher
├── Dockerfile           # Linux container image definition
├── docker-compose.yml   # Multi-platform Docker Compose config
├── spotifetch.service   # Linux systemd background daemon unit
├── downloads/           # Temporary download cache (auto-cleaned)
└── static/
    ├── index.html       # Modern dark-mode Spotify UI
    └── app.js           # Frontend controller, preview drawer, polling
```
