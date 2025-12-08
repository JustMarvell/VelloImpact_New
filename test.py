# # # from youtubesearchpython import *

# # # # video = Video.get('https://www.youtube.com/watch?v=z0GKGpObgPY', mode = ResultMode.json, get_upload_date=True)
# # # # print(video)

# # # videoInfo = Video.getInfo('https://www.youtube.com/watch?v=vv0qwNUMC5A', mode = ResultMode.json)
# # # print(videoInfo)

# # # # videoFormats = Video.getFormats('z0GKGpObgPY')
# # # # print(videoFormats)

# # # from youtubesearchpython import *

# # # suggestions = Suggestions(language = 'en', region = 'US')

# # # print(suggestions.get('1.15 am', mode = ResultMode.json))


# # import requests
# # import json

# # def get_related_videos_debug(video_id, api_key, max_results=5, timeout=10):
# #     """Call YouTube search.list with relatedToVideoId and return detailed debug info.

# #     This helper prints status, headers and the raw response body so you can
# #     see the exact API error. It also includes a fallback suggestion when the
# #     call fails due to SSL/network issues.
# #     """
# #     url = "https://www.googleapis.com/youtube/v3/search"
# #     params = {
# #         "part": "snippet",
# #         "channelId" : 'UCbOCbp5gXL8jigIBZLqMPrw',
# #         "type": "video",
# #         "maxResults": max_results,
# #         "key": api_key
# #     }

# #     try:
# #         resp = requests.get(url, params=params, timeout=timeout)
# #     except requests.exceptions.SSLError as e:
# #         return {"ok": False, "error": "ssl", "exception": str(e), "advice": "There was an SSL error. Try upgrading 'requests' and 'certifi' packages, or verify your network/proxy settings."}
# #     except requests.exceptions.RequestException as e:
# #         return {"ok": False, "error": "network", "exception": str(e), "advice": "Network error when contacting googleapis. Check connectivity, proxies, and firewall."}

# #     result = {"ok": False, "status_code": resp.status_code, "headers": dict(resp.headers)}
# #     text = resp.text
# #     # Try to parse JSON body safely
# #     try:
# #         body = resp.json()
# #     except Exception:
# #         body = text

# #     result["body"] = body

# #     if resp.status_code != 200:
# #         # Provide some tailored advice for common errors
# #         if resp.status_code == 400:
# #             result["advice"] = (
# #                 "HTTP 400: Invalid argument. Common causes: 'relatedToVideoId' used incorrectly, or the API key is restricted."
# #                 "\n - Make sure 'type=video' is present (it is here)."
# #                 "\n - Ensure your API key is valid and the YouTube Data API v3 is enabled for your project."
# #                 "\n - Check API key restrictions in Google Cloud Console (HTTP referrers / IP addresses)."
# #                 "\n - Print 'body' above for the API error message field."
# #             )
# #         elif resp.status_code == 403:
# #             result["advice"] = "HTTP 403: Possibly quota exceeded or API not enabled or API key restricted. Check Google Cloud Console and quotas."
# #         elif resp.status_code == 401:
# #             result["advice"] = "HTTP 401: Unauthorized. Check your API key."
# #         else:
# #             result["advice"] = "See body for details."
# #         return result

# #     # Success
# #     result["ok"] = True
# #     result["items"] = body.get("items") if isinstance(body, dict) else None
# #     return result


# # if __name__ == '__main__':
# #     # Replace with your real key; do NOT commit real keys to source control.
# #     API_KEY = "AIzaSyBs_Oiw8Pjy-CtYGiT4scrwECWmriOkqso"
# #     VIDEO_ID = "vv0qwNUMC5A"

# #     out = get_related_videos_debug(VIDEO_ID, API_KEY)
# #     print(json.dumps(out, indent=2, ensure_ascii=False))

# #     # Quick checklist if you get SSL or 400 errors:
# #     # - SSL EOF: try `pip install --upgrade requests certifi` and retry.
# #     # - 400 INVALID_ARGUMENT: check the printed `body` for the API error details,
# #     #   ensure the API key is enabled for YouTube Data API v3, and check key restrictions.

# """Helper module to fetch song lyrics from Genius API."""

# """Helper module to fetch song lyrics from Genius API."""

# import lyricsgenius
# import settings
# import re
# from typing import Optional, Dict

# # Initialize Genius client (you'll need to set GENIUS_API_TOKEN env var)
# # Get your token from: https://genius.com/api-clients
# GENIUS_TOKEN = settings.GENIUS_API_SECRET
# _genius = None

# # Terms to exclude from song titles when searching for lyrics
# EXCLUDED_TERMS = [
#     "Remix",
#     "Instrumental",
#     "Official Music Video",
#     "Official Video",
#     "Official Audio",
#     "Official Visualizer",
#     "Cover",
#     "Covered By",
#     "Cover By",
#     "Lyrics",
#     "Audio",
#     "Lyric Video",
#     "Vevo",
#     "HD",
#     "4K",
#     "Full Album",
#     "Extended",
#     "Deluxe Edition",
#     "Remaster",
#     "Remastered"
# ]

# if GENIUS_TOKEN:
#     try:
#         _genius = lyricsgenius.Genius(GENIUS_TOKEN, skip_non_songs=True, excluded_terms=EXCLUDED_TERMS)
#     except Exception as e:
#         print(f"Failed to initialize Genius client: {e}")
#         _genius = None


# def clean_song_title(title: str) -> str:
#     """Remove common non-lyrical terms from a song title for better lyrics search.
    
#     Args:
#         title: Original song title (e.g., "Song Title (Official Music Video)")
        
#     Returns:
#         Cleaned song title with excluded terms removed
#     """
#     if not title:
#         return title
    
#     cleaned = title
    
#     # Sort by length (longest first) to match longer terms first
#     # This prevents "Official Video" from matching before "Official Music Video"
#     sorted_terms = sorted(EXCLUDED_TERMS, key=len, reverse=True)
    
#     for term in sorted_terms:
#         # Case-insensitive replacement
#         # Pattern matches: (term), [term], term -, - term, etc.
#         patterns = [
#             rf'\s*\({re.escape(term)}\)',     # (term)
#             rf'\s*\[{re.escape(term)}\]',     # [term]
#             rf'\s*-\s*{re.escape(term)}',     # - term
#             rf'\s*{re.escape(term)}\s*-',     # term -
#             rf'\s+{re.escape(term)}\s*$',     # term at end
#         ]
#         for pattern in patterns:
#             cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
#     # Clean up extra whitespace and dashes
#     cleaned = re.sub(r'\s+', ' ', cleaned).strip()
#     cleaned = re.sub(r'\s*-\s*$', '', cleaned)  # Remove trailing dash
    
#     return cleaned


# def fetch_song_lyrics(song_title: str, artist_name: Optional[str] = None) -> Optional[Dict]:
#     """Fetch lyrics for a song from Genius API.
    
#     Args:
#         song_title: Title of the song to fetch lyrics for
#         artist_name: Optional artist name to improve search accuracy
        
#     Returns:
#         dict with keys:
#             - 'title': Song title
#             - 'artist': Artist name
#             - 'lyrics': Lyrics text (may be truncated if very long)
#             - 'url': Link to Genius page
#             - 'success': True if lyrics were found
#         OR None if Genius is not configured or song not found
#     """
#     if not GENIUS_TOKEN or not _genius:
#         return {
#             'success': False,
#             'error': 'Genius API token not configured. Set GENIUS_API_TOKEN environment variable.'
#         }
    
#     try:
#         # Clean the song title to remove common non-lyrical terms
#         cleaned_title = clean_song_title(song_title)
        
#         # Build search query with cleaned title
#         search_query = f"{cleaned_title} {artist_name}" if artist_name else cleaned_title
        
#         # Search for the song
#         song = _genius.search_song(search_query, get_full_info=True)
        
#         if not song:
#             return {
#                 'success': False,
#                 'error': f'No lyrics found for "{song_title}"'
#             }
        
#         lyrics = song.lyrics
        
#         # Truncate if lyrics are very long (Discord message limit is 2000 chars)
#         max_length = 1900
#         if len(lyrics) > max_length:
#             lyrics = lyrics[:max_length] + "\n\n[Lyrics truncated - visit Genius for full lyrics]"
        
#         return {
#             'success': True,
#             'title': song.title,
#             'artist': song.artist,
#             'lyrics': lyrics,
#             'url': song.url
#         }
    
#     except Exception as e:
#         return {
#             'success': False,
#             'error': f'Error fetching lyrics: {str(e)}'
#         }


# def is_genius_available() -> bool:
#     """Check if Genius API is configured and available."""
#     return GENIUS_TOKEN is not None and _genius is not None


# print(fetch_song_lyrics("back to friends - sombr"))

# def get_random_quotes():
#     import zenquotespy

#     quote = zenquotespy.random()

#     return quote
    
    
# print(get_random_quotes())

# def getException():
#     raise Exception

# if (getException() == Exception("Base Exception")):
#     print("hahah")

import requests
import settings

prompt = 'what can you do?'
url = f'https://api.cookie-api.com/api/ai/message?prompt={prompt}'
headers = {
    'Authorization': settings.COOKIE_API_SECRET
}

response = requests.get(url, headers=headers)
print(response.json())