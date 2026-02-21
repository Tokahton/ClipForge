# ClipForge
ClipForge is a Python tool that turns any web video into a vertical short with captions. You give it a URL (YouTube, Twitch, TikTok, etc.) and it:
1. Downloads the video with yt-dlp
2. Transcribes audio with OpenAI Whisper for word-level timestamps
3. Picks a segment of 30–60 seconds with the most speech (or uses a time you specify)
4. Reformats the clip to 1080×1920 portrait with a blurred background behind the centered video
5. Adds TikTok-style captions – words appear one by one in groups of 3, with the active word highlighted in yellow
6. Exports an MP4 suitable for TikTok/Reels
7. Optionally uploads the clip to TikTok using browser cookies for auth
8. You can process a single video or run a batch of URLs, and it supports cookies for age-restricted or login-only videos.


# Usuage
# Basics Default: auto-select 30–60s segment, add captions
python clip_maker.py https://youtube.com/watch?v=VIDEO_ID

# Custom start time and duration
python clip_maker.py https://youtube.com/watch?v=VIDEO_ID --start 90 --duration 40

# Custom output path
python clip_maker.py https://youtube.com/watch?v=VIDEO_ID -o C:\path\to\my_short.mp4

# Caption options
Better captions (slower, more VRAM)
python clip_maker.py URL --model medium

# No captions
python clip_maker.py URL --no-captions

# Custom caption size
python clip_maker.py URL --font-size 90

# Age-restricted / login-only videos
# Use cookies from Chrome
python clip_maker.py URL --cookies-from-browser chrome

# Use a cookies.txt file
python clip_maker.py URL --cookies www.youtube.com_cookies.txt

# Upload to TikTok
# Single video
python clip_maker.py URL --tiktok --tiktok-description "Check this out! #viral #fyp"

# Batch with per-clip description
python clip_maker.py URL1 URL2 URL3 --tiktok --tiktok-description "Part {n} #series"

# Other sites

python clip_maker.py https://twitch.tv/videos/123456789
python clip_maker.py https://example.com/video.mp4

# Batch processing
python clip_maker.py URL1 URL2 URL3
python clip_maker.py URL1 URL2 --duration 45 --model medium
<img width="360" height="360" alt="image" src="https://github.com/user-attachments/assets/4b6d8ddd-6cf2-46b6-be4c-5135b3c2f9f1" />
