"""Channel-based genre inference helper.

This module provides a simple, metadata-first approach to infer a channel's
likely genre using the channel title and description returned by
`youtubesearchpython.Channel.get`.

It's intentionally lightweight: it uses keyword matching against a
small, extendable mapping and caches results in-memory to avoid repeated
lookups. This is suitable as a first-pass bias for autoplay suggestions.
"""
from typing import Optional, Dict
from youtubesearchpython import Channel
import re

channel_genre_cache: Dict[str, Dict] = {}
_CACHE_MAX = 200

GENRE_KEYWORDS = {
    "lofi": [r"lo-?fi", r"chillhop", r"chill beats", r"lofi"],
    "hiphop": [r"hip[ -]?hop", r"rap", r"trap"],
    "electronic": [r"electro", r"edm", r"house", r"techno", r"trance", r"dubstep"],
    "pop": [r"pop", r"k-pop", r"kpop"],
    "rock": [r"rock", r"metal", r"punk"],
    "classical": [r"classical", r"orchestra", r"symphony", r"concerto"],
    "soundtrack": [r"ost|soundtrack|sound track|anime opening|anime op|anime ending|vgm|video game music|game soundtrack"],
    "remix": [r"remix", r"rework", r"edit"],
    "acoustic": [r"acoustic", r"unplugged", r"instrumental"],
}


def _make_cache_key(channel_id: str) -> str:
    return str(channel_id)


def _cache_set(channel_id: str, value: Dict) -> None:
    key = _make_cache_key(channel_id)
    if key in channel_genre_cache:
        channel_genre_cache[key] = value
        return
    if len(channel_genre_cache) >= _CACHE_MAX:
        channel_genre_cache.pop(next(iter(channel_genre_cache)))
    channel_genre_cache[key] = value


def _cache_get(channel_id: str) -> Optional[Dict]:
    return channel_genre_cache.get(_make_cache_key(channel_id))


def infer_channel_genre(channel_id: str) -> Dict:
    """Infer a normalized genre label from a YouTube channel's metadata.

    Args:
        channel_id: YouTube channel id (e.g. UCxxxxxxxx)

    Returns:
        dict: {"genre": Optional[str], "source": str, "confidence": float}
    """
    if not channel_id:
        return {"genre": None, "source": "none", "confidence": 0.0}

    cached = _cache_get(channel_id)
    if cached:
        return cached

    text = ""
    try:
        info = Channel.get(channel_id)
        title = (info.get("title") or "").lower()
        description = (info.get("description") or "").lower()
        text = f"{title} \n {description}"
    except Exception:
        res = {"genre": None, "source": "fetch_error", "confidence": 0.0}
        _cache_set(channel_id, res)
        return res

    for genre, patterns in GENRE_KEYWORDS.items():
        for pat in patterns:
            try:
                if re.search(pat, title, flags=re.I):
                    res = {"genre": genre, "source": "title", "confidence": 0.95}
                    _cache_set(channel_id, res)
                    return res
            except re.error:
                continue

    for genre, patterns in GENRE_KEYWORDS.items():
        for pat in patterns:
            try:
                if re.search(pat, description, flags=re.I):
                    res = {"genre": genre, "source": "description", "confidence": 0.8}
                    _cache_set(channel_id, res)
                    return res
            except re.error:
                continue

    if "music" in text:
        res = {"genre": "music", "source": "keyword", "confidence": 0.5}
        _cache_set(channel_id, res)
        return res

    res = {"genre": None, "source": "none", "confidence": 0.0}
    _cache_set(channel_id, res)
    return res
