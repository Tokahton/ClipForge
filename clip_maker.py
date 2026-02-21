"""
ClipForge - Automatic Short-Form Video Creator
================================================
Downloads any video, crops to 9:16 portrait (1080x1920),
trims to 30-60 seconds, adds word-by-word captions, and exports.
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
import textwrap
from datetime import datetime

# ---- Pre-flight: detect bad Python (Windows Store stub) ------------------
_this_python = sys.executable
if "WindowsApps" in _this_python:
    print(
        "ERROR: You are running the Windows Store Python stub.\n"
        "       Run this script with the full path to your real Python, e.g.:\n"
        '       "C:\\Path\\To\\Python\\python.exe" clip_maker.py URL\n'
        "\n"
        "       Or remove the Windows Store alias:\n"
        "       Settings -> Apps -> App execution aliases -> turn off 'python.exe' and 'python3.exe'"
    )
    sys.exit(1)

# ---- Third-party imports -------------------------------------------------
try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import yt_dlp
    import whisper
except ImportError as e:
    print(f"ERROR: Missing dependency: {e}")
    print("       Run:  pip install -r requirements.txt")
    sys.exit(1)

import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

try:
    from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
except ImportError:
    try:
        from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
    except ImportError:
        print("ERROR: moviepy is not installed or broken.")
        print("       Run:  pip install moviepy<2.0")
        sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
TARGET_FPS = 30
FONT_SIZE = 72
WORDS_PER_PHRASE = 3
HIGHLIGHT_COLOR = (255, 255, 50)   # yellow for the active word
TEXT_COLOR = (255, 255, 255)        # white for other words
STROKE_COLOR = (0, 0, 0)           # black outline
STROKE_WIDTH = 5
WHISPER_MODEL = "base"
DEFAULT_COOKIES = os.path.join(os.path.expanduser("~"), ".clipforge", "cookies.txt")
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "clipforge_output")


# ---------------------------------------------------------------------------
# Ensure ffmpeg is reachable (moviepy bundles one via imageio-ffmpeg)
# ---------------------------------------------------------------------------
def _ensure_ffmpeg():
    if shutil.which("ffmpeg"):
        return
    try:
        import imageio_ffmpeg
        ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
        os.environ["PATH"] += os.pathsep + ffmpeg_dir
    except ImportError:
        pass
    if not shutil.which("ffmpeg"):
        print(
            "ERROR: ffmpeg not found.\n"
            "Install it with:  winget install ffmpeg\n"
            "Or download from: https://ffmpeg.org/download.html"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Font discovery
# ---------------------------------------------------------------------------
def _find_font(size):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Unique output filename from video title
# ---------------------------------------------------------------------------
def _unique_output_path(title, directory=OUTPUT_DIR):
    safe = re.sub(r'[<>:"/\\|?*]', "", title)
    safe = safe.strip(". ")
    if not safe:
        safe = "clip"
    safe = safe[:80]

    os.makedirs(directory, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{safe}_{stamp}.mp4"
    path = os.path.join(directory, name)

    counter = 2
    while os.path.exists(path):
        name = f"{safe}_{stamp}_{counter}.mp4"
        path = os.path.join(directory, name)
        counter += 1

    return path


# ---------------------------------------------------------------------------
# Step 1 - Download
# ---------------------------------------------------------------------------
def download(url, work_dir, cookies=None, cookies_from_browser=None):
    print("\n[1/6] Downloading video ...")
    opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "outtmpl": os.path.join(work_dir, "source.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [
            lambda d: print(
                f"       {d.get('_percent_str', '').strip()} "
                f"{d.get('_speed_str', '').strip()}",
                end="\r",
            )
            if d["status"] == "downloading"
            else None
        ],
    }
    if cookies:
        opts["cookiefile"] = cookies
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)

    title = info.get("title", "clip") or "clip"
    base, _ = os.path.splitext(path)
    mp4 = base + ".mp4"
    result = mp4 if os.path.exists(mp4) else path
    print(f"       Downloaded -> {os.path.basename(result)}")
    return result, title


# ---------------------------------------------------------------------------
# Step 2 - Transcribe with Whisper
# ---------------------------------------------------------------------------
def transcribe(video_path, model_name):
    print(f"\n[2/6] Transcribing audio (whisper-{model_name}) ...")
    model = whisper.load_model(model_name)
    result = model.transcribe(video_path, word_timestamps=True)

    words = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            words.append(
                {"word": w["word"].strip(), "start": w["start"], "end": w["end"]}
            )
    print(f"       {len(words)} words detected")
    return words


# ---------------------------------------------------------------------------
# Step 3 - Find the densest speech segment
# ---------------------------------------------------------------------------
def best_segment(words, vid_dur, min_s=30, max_s=60):
    if not words or vid_dur <= max_s:
        return 0.0, min(vid_dur, max_s)

    best_start, best_n = 0.0, 0
    for w in words:
        t0 = w["start"]
        t1 = t0 + max_s
        if t1 > vid_dur:
            break
        n = sum(1 for x in words if t0 <= x["start"] < t1)
        if n > best_n:
            best_n, best_start = n, t0

    duration = min(max_s, vid_dur - best_start)
    duration = max(min_s, duration)
    return best_start, duration


# ---------------------------------------------------------------------------
# Step 4 - Crop / resize to 1080x1920 portrait
# ---------------------------------------------------------------------------
def to_portrait(clip):
    print(f"\n[4/6] Converting to {OUTPUT_WIDTH}x{OUTPUT_HEIGHT} portrait ...")
    w, h = clip.size
    target_ratio = OUTPUT_WIDTH / OUTPUT_HEIGHT

    # --- Foreground: scale the full video to fit inside the frame ----------
    if w / h > target_ratio:
        fg_scale = OUTPUT_WIDTH / w
    else:
        fg_scale = OUTPUT_HEIGHT / h
    fg = clip.resize(fg_scale)

    # --- Background: scale video to *fill* the frame, crop, blur + darken -
    if w / h > target_ratio:
        bg_scale = OUTPUT_HEIGHT / h
    else:
        bg_scale = OUTPUT_WIDTH / w
    bg = clip.resize(bg_scale)

    bw, bh = bg.size
    x1 = (bw - OUTPUT_WIDTH) // 2
    y1 = (bh - OUTPUT_HEIGHT) // 2
    bg = bg.crop(x1=max(x1, 0), y1=max(y1, 0),
                 x2=max(x1, 0) + OUTPUT_WIDTH,
                 y2=max(y1, 0) + OUTPUT_HEIGHT)

    def _blur_and_dim(frame):
        img = Image.fromarray(frame)
        img = img.filter(ImageFilter.GaussianBlur(radius=25))
        arr = np.array(img, dtype=np.float32) * 0.35
        return arr.astype(np.uint8)

    bg = bg.fl_image(_blur_and_dim)

    # --- Composite: blurred bg + sharp fg centered -------------------------
    fg = fg.set_position("center")
    return CompositeVideoClip([bg, fg], size=(OUTPUT_WIDTH, OUTPUT_HEIGHT))


# ---------------------------------------------------------------------------
# Step 5 - Build animated captions
# ---------------------------------------------------------------------------
def _group_phrases(words, n=WORDS_PER_PHRASE):
    phrases = []
    for i in range(0, len(words), n):
        grp = words[i : i + n]
        phrases.append(
            {
                "words": grp,
                "start": grp[0]["start"],
                "end": grp[-1]["end"],
                "text": " ".join(g["word"] for g in grp),
            }
        )
    return phrases


def _render_caption(phrase, active_idx, width, height, font):
    """Render one caption state as an RGBA numpy array (small overlay)."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = (height - FONT_SIZE) // 2

    full_text = phrase["text"].upper()
    bb = draw.textbbox((0, 0), full_text, font=font)
    text_w = bb[2] - bb[0]
    x = (width - text_w) // 2

    for i, w_info in enumerate(phrase["words"]):
        token = w_info["word"].upper()
        spacer = " " if i < len(phrase["words"]) - 1 else ""
        display = token + spacer
        fill = HIGHLIGHT_COLOR if i == active_idx else TEXT_COLOR

        draw.text(
            (x, y),
            display,
            font=font,
            fill=fill,
            stroke_width=STROKE_WIDTH,
            stroke_fill=STROKE_COLOR,
        )
        tw = draw.textbbox((0, 0), display, font=font)
        x += tw[2] - tw[0]

    return np.array(img)


def add_captions(clip, words, seg_start, seg_end, font_size):
    seg_words = [w for w in words if seg_start <= w["start"] < seg_end]
    if not seg_words:
        print("       No speech detected in segment - skipping captions")
        return clip

    phrases = _group_phrases(seg_words)
    font = _find_font(font_size)
    caption_h = font_size * 3
    y_pos = int(OUTPUT_HEIGHT * 0.70)

    layers = [clip]
    print(f"\n[5/6] Rendering {len(phrases)} caption phrases ...")

    GAP = 0.08  # seconds of blank space between phrases

    for pi, phrase in enumerate(phrases):
        # Hard deadline: this phrase must vanish before the next one starts
        if pi + 1 < len(phrases):
            phrase_deadline = phrases[pi + 1]["start"] - seg_start - GAP
        else:
            phrase_deadline = clip.duration

        for wi, word in enumerate(phrase["words"]):
            rgba = _render_caption(phrase, wi, OUTPUT_WIDTH, caption_h, font)

            t0 = word["start"] - seg_start
            if wi + 1 < len(phrase["words"]):
                t1 = phrase["words"][wi + 1]["start"] - seg_start
            else:
                t1 = phrase["end"] - seg_start + 0.20

            t0 = max(0.0, t0)
            t1 = min(t1, phrase_deadline, clip.duration)
            if t1 <= t0:
                continue

            rgb = rgba[:, :, :3]
            alpha = rgba[:, :, 3].astype(np.float64) / 255.0

            ic = (
                ImageClip(rgb)
                .set_duration(t1 - t0)
                .set_start(t0)
                .set_position((0, y_pos))
            )
            ic = ic.set_mask(
                ImageClip(alpha, ismask=True).set_duration(t1 - t0)
            )
            layers.append(ic)

    return CompositeVideoClip(layers, size=(OUTPUT_WIDTH, OUTPUT_HEIGHT))


# ---------------------------------------------------------------------------
# Step 6 - Export
# ---------------------------------------------------------------------------
def export(clip, path):
    print(f"\n[6/6] Exporting -> {path}")
    clip.write_videofile(
        path,
        fps=TARGET_FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="8000k",
        preset="medium",
        threads=os.cpu_count() or 4,
    )


# ---------------------------------------------------------------------------
# Step 7 (optional) - Upload to TikTok
# ---------------------------------------------------------------------------
def upload_to_tiktok(video_path, description="", cookies=DEFAULT_COOKIES):
    """Upload the finished video to TikTok using browser-cookie auth."""
    try:
        from tiktok_uploader.upload import upload_video
    except ImportError:
        print(
            "\n  TikTok upload SKIPPED — missing dependency.\n"
            "  Install with:\n"
            "    pip install tiktok-uploader\n"
            "    playwright install\n"
        )
        return False

    if not os.path.isfile(cookies):
        print(
            f"\n  TikTok upload SKIPPED — cookie file not found: {cookies}\n"
            "  To set up TikTok uploads:\n"
            "    1. Install the 'Get cookies.txt LOCALLY' Chrome extension\n"
            "    2. Go to tiktok.com and log in\n"
            "    3. Click the extension -> export cookies for this site\n"
            f"    4. Save the file to: {cookies}\n"
        )
        return False

    print(f"\n[7/7] Uploading to TikTok ...")
    print(f"       Description: {description[:80]}{'...' if len(description) > 80 else ''}")

    try:
        upload_video(
            filename=video_path,
            description=description,
            cookies=cookies,
            headless=True,
        )
        print("       Upload complete!")
        return True
    except Exception as exc:
        print(f"       Upload FAILED: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------
def run(
    url,
    output=None,
    start=None,
    duration=None,
    model=WHISPER_MODEL,
    font_size=FONT_SIZE,
    no_captions=False,
    tiktok=False,
    tiktok_description="",
    tiktok_cookies=DEFAULT_COOKIES,
    cookies=None,
    cookies_from_browser=None,
):
    _ensure_ffmpeg()
    work_dir = tempfile.mkdtemp(prefix="clipforge_")

    try:
        # Download
        src, title = download(url, work_dir, cookies=cookies,
                              cookies_from_browser=cookies_from_browser)

        # Transcribe (unless skipped)
        words = [] if no_captions else transcribe(src, model)

        # Load source video
        clip = VideoFileClip(src)
        print(f"       Source: {clip.size[0]}x{clip.size[1]}, {clip.duration:.1f}s")

        # Choose segment
        if start is not None:
            seg_start = start
            seg_dur = duration or 45
        else:
            print("\n[3/6] Selecting best segment ...")
            seg_start, seg_dur = best_segment(
                words,
                clip.duration,
                min_s=duration or 30,
                max_s=duration or 60,
            )

        seg_end = min(seg_start + seg_dur, clip.duration)
        print(f"       Segment: {seg_start:.1f}s -> {seg_end:.1f}s ({seg_end - seg_start:.1f}s)")

        # Trim
        trimmed = clip.subclip(seg_start, seg_end)

        # Portrait crop
        portrait = to_portrait(trimmed)

        # Captions
        if no_captions:
            final = portrait
        else:
            final = add_captions(portrait, words, seg_start, seg_end, font_size)

        # Export
        if output is None:
            output = _unique_output_path(title)

        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        export(final, output)

        for c in (clip, trimmed, portrait, final):
            try:
                c.close()
            except Exception:
                pass

        print(f"\n  Done!  ->  {output}\n")

        if tiktok:
            upload_to_tiktok(output, tiktok_description, tiktok_cookies)

        return output

    except Exception as exc:
        print(f"\n  Error: {exc}", file=sys.stderr)
        raise


# ---------------------------------------------------------------------------
# Batch processing (sequential queue — one at a time)
# ---------------------------------------------------------------------------
import time


def run_batch(urls, **kwargs):
    """Process URLs one at a time in order (queue)."""
    _ensure_ffmpeg()

    total = len(urls)
    print(f"\n  Queue: {total} video(s) — processing one at a time")
    print(f"  Output folder: {OUTPUT_DIR}\n")
    start_t = time.time()
    results = []

    for i, url in enumerate(urls, start=1):
        print(f"\n{'='*60}")
        print(f"  CLIP {i}/{total}  —  {url}")
        print(f"{'='*60}")

        run_kwargs = {**kwargs}
        tiktok_desc = run_kwargs.get("tiktok_description", "")
        if tiktok_desc and "{n}" in tiktok_desc:
            run_kwargs["tiktok_description"] = tiktok_desc.replace("{n}", str(i))

        try:
            out = run(url=url, **run_kwargs)
            results.append((i, url, out, None))
        except Exception as exc:
            results.append((i, url, None, str(exc)))

    elapsed = time.time() - start_t
    print(f"\n{'='*60}")
    print(f"  BATCH COMPLETE  ({elapsed:.0f}s)")
    print(f"{'='*60}")
    for idx, url, out, err in results:
        if err:
            print(f"  [{idx}] FAILED  — {err}")
        else:
            print(f"  [{idx}] OK      — {out}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    banner = r"""
   ____ _ _       _____
  / ___| (_)_ __ |  ___|__  _ __ __ _  ___
 | |   | | | '_ \| |_ / _ \| '__/ _` |/ _ \
 | |___| | | |_) |  _| (_) | | | (_| |  __/
  \____|_|_| .__/|_|  \___/|_|  \__, |\___|
            |_|                  |___/
    """
    print(banner)

    ap = argparse.ArgumentParser(
        prog="clipforge",
        description="Turn any video into a captioned vertical short.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
        examples:
          Single video:
            python clip_maker.py https://youtube.com/watch?v=XXXX

          Multiple videos (queued, one at a time):
            python clip_maker.py URL1 URL2 URL3

          Options apply to all videos in a batch:
            python clip_maker.py URL1 URL2 --duration 45 --model medium
        """),
    )
    ap.add_argument(
        "urls",
        nargs="+",
        metavar="URL",
        help="Video URL(s) — processed in queue order (YouTube, Twitch, or any supported site)",
    )
    ap.add_argument("-o", "--output", help="Output file path (only used for single URL)")
    ap.add_argument("-s", "--start", type=float, help="Start time in seconds (auto if omitted)")
    ap.add_argument("-d", "--duration", type=float, help="Clip duration in seconds  [30-60 auto]")
    ap.add_argument(
        "-m",
        "--model",
        default=WHISPER_MODEL,
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size  [base]",
    )
    ap.add_argument("--font-size", type=int, default=FONT_SIZE, help="Caption font size  [72]")
    ap.add_argument("--no-captions", action="store_true", help="Skip caption generation")

    cookie_grp = ap.add_argument_group("cookies (for age-restricted / login-required videos)")
    cookie_grp.add_argument(
        "--cookies",
        metavar="FILE",
        help="Path to a Netscape-format cookies.txt file for yt-dlp",
    )
    cookie_grp.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        choices=["chrome", "firefox", "edge", "brave", "opera", "safari", "vivaldi", "chromium"],
        help="Auto-extract cookies from browser (chrome, firefox, edge, brave, opera, safari, vivaldi, chromium)",
    )

    tiktok_grp = ap.add_argument_group("TikTok upload")
    tiktok_grp.add_argument(
        "--tiktok",
        action="store_true",
        help="Upload finished clip(s) to TikTok after export",
    )
    tiktok_grp.add_argument(
        "--tiktok-description",
        default="",
        metavar="DESC",
        help="Video description / hashtags (use {n} for clip number in batch mode)",
    )
    tiktok_grp.add_argument(
        "--tiktok-cookies",
        default=DEFAULT_COOKIES,
        metavar="FILE",
        help=f"Path to TikTok cookies.txt  [{DEFAULT_COOKIES}]",
    )

    args = ap.parse_args()

    shared = dict(
        start=args.start,
        duration=args.duration,
        model=args.model,
        font_size=args.font_size,
        no_captions=args.no_captions,
        cookies=args.cookies,
        cookies_from_browser=args.cookies_from_browser,
        tiktok=args.tiktok,
        tiktok_description=args.tiktok_description,
        tiktok_cookies=args.tiktok_cookies,
    )

    if len(args.urls) == 1:
        run(url=args.urls[0], output=args.output, **shared)
    else:
        if args.output:
            print("  Note: --output is ignored in batch mode (each clip gets an auto-name)")
        run_batch(args.urls, **shared)


if __name__ == "__main__":
    main()
