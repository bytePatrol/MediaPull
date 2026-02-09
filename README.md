<p align="center">
  <img src="src-tauri/icons/MediaPull.png" width="128" height="128" alt="Media Pull">
</p>

<h1 align="center">Media Pull</h1>

<p align="center">
  <strong>Download YouTube videos in up to 4K quality with automatic ad & sponsor removal.</strong>
</p>

<p align="center">
  A native macOS desktop app built with Tauri, powered by yt-dlp and ffmpeg.
</p>

<p align="center">
  <a href="https://github.com/bytePatrol/MediaPull/releases/latest"><img src="https://img.shields.io/github/v/release/bytePatrol/MediaPull?style=flat-square&color=2E7CF6" alt="Release"></a>
  <a href="https://github.com/bytePatrol/MediaPull/releases/latest"><img src="https://img.shields.io/github/downloads/bytePatrol/MediaPull/total?style=flat-square&color=34C759" alt="Downloads"></a>
  <a href="#license"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License"></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-macOS-lightgrey?style=flat-square&logo=apple" alt="macOS"></a>
</p>

---

## Features

### Video Downloads
- **Up to 4K resolution** &mdash; download in 2160p, 1440p, 1080p, 720p, or 480p
- **Audio-only mode** &mdash; extract audio as high-quality M4A files
- **Smart format selection** &mdash; automatically picks the best codec (H.264, VP9, AV1) per resolution
- **Hardware-accelerated encoding** &mdash; uses Apple VideoToolbox (GPU) with automatic CPU fallback

### SponsorBlock Integration
- **Automatic sponsor removal** &mdash; strips ads, intros, outros, self-promotions, and filler
- **Community-powered** &mdash; leverages the SponsorBlock database with 8 configurable categories
- **Smart auto-disable** &mdash; automatically skips SponsorBlock when downloading chapters (timestamps would shift)

### Chapter Downloads
- **Split by chapter** &mdash; download individual chapters as separate files
- **Instant splitting** &mdash; uses stream copy (no re-encoding) for chapter extraction
- **Organized output** &mdash; saves to `Video Title/01 - Chapter Name.mp4`

### Playlist Downloads
- **Batch download** &mdash; download entire playlists sequentially
- **Selective downloading** &mdash; pick which videos to include with select all/none controls
- **Organized output** &mdash; creates a subfolder named after the playlist
- **Resilient** &mdash; continues to the next video if one fails, with per-video progress tracking
- **Cancellable** &mdash; stop after the current video finishes

### Additional Features
- **Trim/clip support** &mdash; download a specific time range of any video
- **Cookie authentication** &mdash; access age-restricted and members-only content via browser cookies
- **Configurable bitrate** &mdash; auto, per-resolution, or custom bitrate encoding modes
- **Download history** &mdash; searchable library of past downloads
- **Auto-update** &mdash; checks for yt-dlp updates and installs with one click
- **Retry system** &mdash; up to 6 retries with progressive delays for reliability
- **Real-time progress** &mdash; speed, ETA, and percentage displayed in the status bar
- **Activity log** &mdash; detailed logging with export capability
- **Keyboard shortcuts** &mdash; `Cmd+V` to paste, `Cmd+Enter` to download

---

## Screenshots

<p align="center">
  <img src="https://github.com/user-attachments/assets/placeholder-main" width="800" alt="Media Pull — Main Interface">
</p>

<p align="center">
  <em>Analyze any YouTube video and choose your preferred quality</em>
</p>

<p align="center">
  <img src="https://github.com/user-attachments/assets/placeholder-playlist" width="800" alt="Media Pull — Playlist Downloads">
</p>

<p align="center">
  <em>Download entire playlists with selective video picking</em>
</p>

---

## Installation

### Download
Grab the latest `.dmg` from the [Releases](https://github.com/bytePatrol/MediaPull/releases/latest) page.

1. Open the `.dmg` file
2. Drag **Media Pull** to your Applications folder
3. On first launch, right-click the app and select **Open** (macOS Gatekeeper)

### Requirements
- **macOS 11+** (Big Sur or later, Apple Silicon native)
- **yt-dlp** &mdash; installed via Homebrew (`brew install yt-dlp`) or managed by the app
- **ffmpeg** &mdash; installed via Homebrew (`brew install ffmpeg`) or bundled
- **Python 3.9+** &mdash; included with macOS

---

## How It Works

Media Pull uses a multi-stage pipeline for maximum quality:

```
Analyze  →  Download Video  →  Download Audio  →  Merge & Encode  →  SponsorBlock  →  Done
                (yt-dlp)          (yt-dlp)         (ffmpeg/GPU)       (optional)
```

1. **Analyze** &mdash; fetches video metadata, available formats, chapters, and thumbnail via yt-dlp
2. **Download** &mdash; downloads separate video and audio streams at the highest available quality
3. **Encode** &mdash; merges streams into a single MP4 using hardware-accelerated H.264 encoding
4. **SponsorBlock** &mdash; queries the SponsorBlock API and removes matched segments via ffmpeg
5. **Chapters** (optional) &mdash; splits the encoded file into individual chapter files using stream copy

---

## Architecture

```
┌──────────────────────────────────────────────┐
│              Frontend (HTML/CSS/JS)          │
│   index.html + src/main.js + components/    │
└──────────────┬───────────────────────────────┘
               │  Tauri invoke() / listen()
┌──────────────▼───────────────────────────────┐
│              Rust Backend (Tauri v2)         │
│   src-tauri/src/commands/*.rs               │
│   IPC bridge, process management            │
└──────────────┬───────────────────────────────┘
               │  stdin/stdout JSON lines
┌──────────────▼───────────────────────────────┐
│              Python Modules                  │
│   python/download.py  — download pipeline   │
│   python/analyze.py   — video/playlist info │
│   python/convert.py   — ffmpeg encoding     │
│   python/chapters.py  — chapter splitting   │
│   python/sponsorblock.py — segment removal  │
│   python/cookies.py   — browser cookie mgmt │
└──────────────────────────────────────────────┘
```

- **Frontend** &mdash; vanilla HTML/CSS/JS, no framework, no build step
- **Rust** &mdash; Tauri v2 shell, manages Python subprocesses, emits events to frontend
- **Python** &mdash; each module writes JSON lines to stdout, parsed by Rust in real-time

---

## Building from Source

```bash
# Prerequisites
brew install yt-dlp ffmpeg node rust

# Clone
git clone https://github.com/bytePatrol/MediaPull.git
cd MediaPull

# Install JS dependencies
npm install

# Development (hot-reload)
npx tauri dev

# Production build
npm run tauri:build
```

The built app will be at `src-tauri/target/release/bundle/macos/Media Pull.app`.

---

## Configuration

Settings are stored in `~/.config/media-pull/`:

| File | Purpose |
|------|---------|
| `config.json` | Output directory and app config |
| `settings.json` | Cookies, SponsorBlock, encoding preferences |
| `history.json` | Download history |

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with <a href="https://v2.tauri.app">Tauri</a> + <a href="https://github.com/yt-dlp/yt-dlp">yt-dlp</a> + <a href="https://ffmpeg.org">ffmpeg</a>
</p>
