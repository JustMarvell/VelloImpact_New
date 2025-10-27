import requests
import settings
import yt_dlp

proxy = settings.YOUTUBE_PROXY_SECRET


ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info('https://www.youtube.com/watch?v=YQHsXMglC9A', download=False)
    print(info['thumbnail'])