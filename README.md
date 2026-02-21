# ClipForge

Automatic short-form video creator. Give it any video link (YouTube, Twitch, etc.) and it will:

1. **Download** the video
2. **Transcribe** the audio to get word-level timestamps
3. **Pick the best 30-60 second segment** (densest speech)
4. **Crop to 1080x1920** vertical portrait format
5. **Add word-by-word captions** (TikTok/Reels style)
6. **Export** a ready-to-upload MP4
7. **(Optional) Auto-upload to TikTok**

## Setup

### 1. Install Python 3.9+

Download from [python.org](https://www.python.org/downloads/) if you don't have it.
Make sure to check **"Add Python to PATH"** during install.

### 2. Install ffmpeg

```
winget install ffmpeg
```

Or download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to your PATH.

> **Note:** moviepy bundles a minimal ffmpeg via `imageio-ffmpeg`, so this step may
> be optional — but having a system ffmpeg is recommended for best compatibility.

### 3. Install Python dependencies

Open a terminal in the ClipForge folder and run:

```
pip install -r requirements.txt
```

> **Heads up:** `openai-whisper` installs PyTorch (~2 GB). If you have an NVIDIA GPU,
> install the CUDA version of PyTorch first for much faster transcription:
> https://pytorch.org/get-started/locally/

### 4. (Optional) Set up TikTok auto-upload

If you want ClipForge to upload clips to TikTok automatically:

```bash
# Install Playwright browsers (one-time setup)
playwright install
```

Then export your TikTok cookies:

1. Install the **"Get cookies.txt LOCALLY"** Chrome extension
2. Go to [tiktok.com](https://www.tiktok.com) and **log in** to your account
3. Click the extension icon -> **Export** cookies for this site
4. Save the file to `~/.clipforge/cookies.txt` (or anywhere — pass the path with `--tiktok-cookies`)

> **Important:** Logging out of TikTok in your browser will invalidate the cookies.
> Re-export them if uploads start failing.

## Usage

```
python clip_maker.py <VIDEO_URL> [options]
```

### Examples

```bash
# Basic - auto-selects best 30-60s segment
python clip_maker.py https://youtube.com/watch?v=VIDEO_ID

# Custom start time and duration
python clip_maker.py https://youtube.com/watch?v=VIDEO_ID --start 90 --duration 40

# Custom output path
python clip_maker.py URL -o my_short.mp4

# Better captions (slower, uses more VRAM)
python clip_maker.py URL --model medium

# Skip captions entirely
python clip_maker.py URL --no-captions

# Twitch clip
python clip_maker.py https://twitch.tv/videos/123456789

# Any direct video URL
python clip_maker.py https://example.com/video.mp4

# Age-restricted / members-only YouTube video (auto-grab cookies from Chrome)
python clip_maker.py https://youtube.com/watch?v=RESTRICTED --cookies-from-browser chrome

# Or use a cookies.txt file instead
python clip_maker.py URL --cookies cookies.txt

# Auto-upload to TikTok after export
python clip_maker.py URL --tiktok --tiktok-description "Check this out! #viral #fyp"

# Batch mode with TikTok upload (each clip gets uploaded)
python clip_maker.py URL1 URL2 URL3 --tiktok --tiktok-description "Part {n} #series"

# Custom cookies path
python clip_maker.py URL --tiktok --tiktok-cookies ~/.clipforge/cookies.txt
```

### All Options

| Flag              | Description                                | Default                     |
|-------------------|--------------------------------------------|-----------------------------|
| `url`             | Video URL (positional, required)           | —                           |
| `-o`, `--output`  | Output file path                           | `~/Desktop/clipforge_output/` |
| `-s`, `--start`   | Start time in seconds                      | Auto (best segment)         |
| `-d`, `--duration` | Clip duration in seconds                  | 30-60 (auto)                |
| `-m`, `--model`   | Whisper model: tiny/base/small/medium/large | `base`                     |
| `--font-size`     | Caption font size                          | `72`                        |
| `--no-captions`   | Skip caption generation                    | Off                         |
| `--cookies`       | Path to Netscape-format cookies.txt for yt-dlp | —                        |
| `--cookies-from-browser` | Auto-extract cookies from browser (chrome, firefox, edge, brave, etc.) | — |
| `--tiktok`        | Upload to TikTok after export              | Off                         |
| `--tiktok-description` | Video description & hashtags (use `{n}` for clip # in batch) | `""` |
| `--tiktok-cookies` | Path to cookies.txt file                  | `~/.clipforge/cookies.txt`  |

## Whisper Model Comparison

| Model    | Speed  | Accuracy | VRAM   |
|----------|--------|----------|--------|
| `tiny`   | Fastest | Lower   | ~1 GB  |
| `base`   | Fast   | Good     | ~1 GB  |
| `small`  | Medium | Better   | ~2 GB  |
| `medium` | Slow   | Great    | ~5 GB  |
| `large`  | Slowest | Best    | ~10 GB |

## Supported Sites

Any site supported by [yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), including:

- YouTube (videos, shorts, live replays)
- Twitch (VODs, clips, highlights)
- TikTok
- Instagram Reels
- Twitter/X videos
- Reddit videos
- Facebook videos
- Vimeo
- And 1000+ more
