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
]

if GENIUS_TOKEN:
    try:
        _genius = lyricsgenius.Genius(GENIUS_TOKEN, skip_non_songs=True, excluded_terms=EXCLUDED_TERMS)
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


async def fetch_song_lyrics(song_title: str, artist_name: Optional[str] = None) -> Optional[Dict]:
    """Fetch lyrics for a song from Genius API.
    
    Args:
        song_title: Title of the song to fetch lyrics for
        artist_name: Optional artist name to improve search accuracy
        
    Returns:
        dict with keys:
            - 'title': Song title
            - 'artist': Artist name
            - 'lyrics': Lyrics text (may be truncated if very long)
            - 'url': Link to Genius page
            - 'success': True if lyrics were found
        OR None if Genius is not configured or song not found
    """
    if not GENIUS_TOKEN or not _genius:
        return {
            'success': False,
            'error': 'Genius API token not configured. Set GENIUS_API_TOKEN environment variable.'
        }
    
    try:
        cleaned_title = clean_song_title(song_title)
        
        print(f"Search query cleaned: {cleaned_title} | artist hint: {artist_name}")

        # Helper: try to fetch a song given title and optional artist hint
        def try_fetch(title_hint: str, artist_hint: Optional[str]):
            q = f"{title_hint} {artist_hint}" if artist_hint else title_hint
            translation_indicators = [
                'translation', 'translations', 'traduc', 'tradu', 'traducción', 'tradução', 'traduction',
                'übersetzung', '訳', '翻訳', '번역', 'ترجمة', 'translated'
            ]

            try:
                search_results = _genius.search_songs(q, per_page=5) or {}
                hits = search_results.get('hits', [])
            except Exception:
                hits = []

            def is_translation_hit(res: dict) -> bool:
                url = (res.get('url') or '').lower()
                title = (res.get('title') or '').lower()
                for ind in translation_indicators:
                    if ind in url or ind in title:
                        return True
                return False

            for hit in hits:
                res = hit.get('result') if isinstance(hit, dict) else None
                if not res:
                    continue
                if is_translation_hit(res):
                    continue
                cand_title = res.get('title') or res.get('title_with_featured') or title_hint
                cand_artist = (res.get('primary_artist') or {}).get('name')
                
                print (f"Cand title : {cand_title}")
                print (f"Cand artist : {cand_artist}")
                try:
                    song_obj = _genius.search_song(cand_title, artist=cand_artist or '', get_full_info=True)
                except Exception:
                    song_obj = None
                if song_obj:
                    return song_obj

            try:
                return _genius.search_song(title_hint, artist=artist_hint or '', get_full_info=True)
            except Exception:
                return None

        song = None

        split_patterns = [' - ', ' – ', ' — ', ':']
        candidates = []
        for sep in split_patterns:
            if sep in cleaned_title:
                left, right = cleaned_title.split(sep, 1)
                left = left.strip()
                right = right.strip()
                # Two possible interpretations: Artist - Title OR Title - Artist
                candidates.append((right, left))  # assume left=artist, right=title
                candidates.append((left, right))  # assume left=title, right=artist
                break

        # Also add the raw cleaned title as a candidate
        candidates.append((cleaned_title, artist_name))

        fallback_song = None
        for title_hint, artist_hint in candidates:
            song = try_fetch(title_hint, artist_hint)
            if song:
                if artist_hint and isinstance(song.artist, str) and artist_hint.lower() in song.artist.lower():
                    break
                if not fallback_song:
                    fallback_song = song

        if not song and fallback_song:
            song = fallback_song

        if not song:
            return {
                'success': False,
                'error': f'No lyrics found for "{song_title}"'
            }

        lyrics = song.lyrics
        
        max_length = 1900
        if len(lyrics) > max_length:
            lyrics = lyrics[:max_length] + "\n\n[Lyrics truncated - visit Genius for full lyrics]"
        
        return {
            'success': True,
            'title': song.title,
            'artist': song.artist,
            'lyrics': lyrics,
            'url': song.url
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Error fetching lyrics: {str(e)}'
        }


def is_genius_available() -> bool:
    """Check if Genius API is configured and available."""
    return GENIUS_TOKEN is not None and _genius is not None
