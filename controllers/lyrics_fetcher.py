"""Helper module to fetch song lyrics from Genius API."""

import lyricsgenius
import settings
import re
from typing import Optional, Dict

GENIUS_TOKEN = settings.GENIUS_API_SECRET
_genius = None

EXCLUDED_TERMS = [
    "Remix",
    "Instrumental",
    "Official Music Video",
    "Official Video",
    "Official Audio",
    "Official Visualizer",
    "Cover",
    "Covered By",
    "Cover By",
    "Lyrics",
    "Audio",
    "Lyric Video",
    "Vevo",
    "HD",
    "4K",
    "Full Album",
    "Extended",
    "Deluxe Edition",
    "Remaster",
    "Remastered",
    "【Original Song】"
    "【Official Animated MV】",
    "Original Song",
    "Official Animated MV",
    "MV",
    "Official",
    "【Original Song】",
    "【Official Animated MV】"
    "Live", 
    "Acoustic", 
    "Piano Version",
    "Slowed + Reverb",
    "Sped Up",
    "Nightcore",
    "8D Audio",
    "Lyrics On Screen",
    "Animation", 
    "AMV",
    "TikTok", 
    "1 Hour",
    "10 Hours", 
    "Loop",
    "Bass Boosted"
]

if GENIUS_TOKEN:
    try:
        _genius = lyricsgenius.Genius(
            GENIUS_TOKEN,
            skip_non_songs=True,
            excluded_terms=EXCLUDED_TERMS,
            timeout=15,
            retries=3,
            sleep_time=0.5
        )
    except Exception as e:
        print(f"Failed to initialize Genius client: {e}")
        _genius = None


def clean_song_title(title: str) -> str:
    """Remove common non-lyrical terms from a song title for better lyrics search.
    
    Args:
        title: Original song title (e.g., "Song Title (Official Music Video)")
        
    Returns:
        Cleaned song title with excluded terms removed
    """
    if not title:
        return title
    
    cleaned = title
    
    sorted_terms = sorted(EXCLUDED_TERMS, key=len, reverse=True)
    
    for term in sorted_terms:
        # Case-insensitive replacement
        # Pattern matches: (term), [term], term -, - term, etc.
        patterns = [
            rf'\s*\({re.escape(term)}\)',     # (term)
            rf'\s*\[{re.escape(term)}\]',     # [term]
            rf'\s*-\s*{re.escape(term)}',     # - term
            rf'\s*{re.escape(term)}\s*-',     # term -
            rf'\s+{re.escape(term)}\s*$',     # term at end
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Clean up extra whitespace and dashes
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'\s*-\s*$', '', cleaned)  # Remove trailing dash
    
    return cleaned
        
async def fetch_song_lyrics(song_title: str, artist_name: Optional[str] = None) -> Dict:
    """Fetch ONLY original-language lyrics — NEVER returns a search list"""
    if not GENIUS_TOKEN or not _genius:
        return {
            'success': False,
            'error': 'Genius API token not configured.'
        }

    try:
        cleaned_title = clean_song_title(song_title)
        query = cleaned_title
        if artist_name:
            query += f" {artist_name}"

        print(f"[Lyrics] Searching: {query}")

        # Comprehensive translation blocklist
        translation_keywords = [
            "translation", "translations", "traduc", "tradução", "traducción", "traduction",
            "übersetzung", "перевод", "번역", "ترجمة", "歌詞", "lyrics in", "sub español",
            "english", "spanish", "portuguese", "french", "german", "russian", "korean",
            "arabic", "chinese", "japanese", "thai", "vietnamese", "italian",
            "english translation", "traducción al español", "tradução em português",
            "traduction française", "deutsche Übersetzung", "перевод на русский",
            "한국어 번역", "日本語訳", "ترجمة عربية", "แปลไทย", "sub indo",
            "pinyin", "hangul"
        ]

        def is_translation(title: str, url: str = "") -> bool:
            text = f"{title} {url}".lower()
            return any(k in text for k in translation_keywords)

        # ── STEP 1: Try direct search (most reliable) ──
        song = _genius.search_song(title=cleaned_title, artist=artist_name, get_full_info=True)

        # Validate it's a real Song object with lyrics
        if song and hasattr(song, 'lyrics') and song.lyrics and not is_translation(song.title, song.url):
            lyrics = song.lyrics.strip()
            if lyrics and len(lyrics) > 50:  # Avoid garbage
                if "Embed" in lyrics[-20:]:
                    lyrics = lyrics.rsplit("Embed", 1)[0].strip()
                return {
                    'success': True,
                    'title': song.title,
                    'artist': song.artist,
                    'lyrics': lyrics,
                    'url': song.url
                }

        # ── FINAL: Nothing found ──
        return {
            'success': False,
            'error': f'No original lyrics found for "{song_title}" try again later or use the /lyrics command instead'
        }

    except Exception as e:
        print(f"[Lyrics] Unexpected error: {e}")
        return {
            'success': False,
            'error': 'Lyrics service temporarily unavailable'
        }

def is_genius_available() -> bool:
    """Check if Genius API is configured and available."""
    return GENIUS_TOKEN is not None and _genius is not None
