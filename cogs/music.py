import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from youtubesearchpython import *
from controllers.channel_genre import infer_channel_genre
from controllers.lyrics_fetcher import fetch_song_lyrics, is_genius_available
import controllers.character_chunk as character_chunk
import yt_dlp
import settings
import time
import concurrent.futures
import threading
import weakref
import aiohttp
import requests
import random
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from collections import defaultdict, deque
from functools import wraps
import logging
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging for performance monitoring
cogs_logger = settings.logging.getLogger("cogs")

# Import network utilities for TLS error handling
try:
    from network_utils import safe_request, monitor_network_health
    NETWORK_UTILS_AVAILABLE = True
except ImportError:
    NETWORK_UTILS_AVAILABLE = False
    cogs_logger.warning("Network utils not available, using fallback TLS error handling")

try:
    from connections.firebase import DEFAULT_TIMEOUT
    FIREBASE_TIMEOUT_AVAILABLE = True
except ImportError:
    FIREBASE_TIMEOUT_AVAILABLE = False

# Create our own session to avoid circular imports
DEFAULT_YOUTUBE_TIMEOUT = 30

# Import Firebase connection utilities safely
try:
    from connections.firebase import FIREBASE_SESSION
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    FIREBASE_SESSION = requests.Session()
    cogs_logger.warning("Firebase not available, using fallback session")

# Define retry decorator for YouTube operations
def retry_on_youtube_error(max_retries=3, delay=1):
    """Decorator for retrying on YouTube/TLS errors"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()
                    # Check for connection/TLS related errors
                    if any(keyword in error_msg for keyword in [
                        'connection', 'tls', 'reset', 'timeout', 'network', 
                        'unreachable', 'temporary failure', 'name resolution',
                        'ssl', 'certificate'
                    ]):
                        if attempt < max_retries - 1:
                            wait_time = delay * (2 ** attempt) + random.uniform(0, 1)
                            cogs_logger.warning(f"YouTube connection error in {func.__name__}, retrying in {wait_time:.2f}s: {e}")
                            await asyncio.sleep(wait_time)
                            continue
                    # Re-raise non-connection errors immediately
                    raise e
            raise Exception(f"Max retries exceeded for {func.__name__}")
        return wrapper
    return decorator

# Create YouTube-specific session with retry strategy for TLS error handling
YOUTUBE_SESSION = requests.Session()

# Configure retry strategy for YouTube operations with TLS error handling
youtube_retry_strategy = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504, 520, 522, 524],  # Include CloudFlare and TLS errors
    allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
    backoff_factor=1,
    raise_on_status=False
)

youtube_adapter = HTTPAdapter(max_retries=youtube_retry_strategy)
YOUTUBE_SESSION.mount("http://", youtube_adapter)
YOUTUBE_SESSION.mount("https://", youtube_adapter)

# Circuit breaker for YouTube operations to prevent cascading failures
class YouTubeCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                cogs_logger.info("YouTube circuit breaker moved to HALF_OPEN state")
            else:
                raise Exception("YouTube circuit breaker is OPEN - preventing cascading failures")
        
        try:
            result = await func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            cogs_logger.warning(f"YouTube circuit breaker moved to OPEN state after {self.failure_count} failures")

# Global YouTube circuit breaker
youtube_circuit_breaker = YouTubeCircuitBreaker(failure_threshold=3, timeout=30)

# YouTube session manager for connection pooling
class YouTubeSessionManager:
    def __init__(self):
        self.session = None
        self._lock = asyncio.Lock()
    
    async def get_session(self):
        async with self._lock:
            if self.session is None:
                timeout = aiohttp.ClientTimeout(total=DEFAULT_YOUTUBE_TIMEOUT, connect=10)
                self.session = aiohttp.ClientSession(
                    timeout=timeout,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36'
                    }
                )
            return self.session
    
    async def close(self):
        async with self._lock:
            if self.session:
                await self.session.close()
                self.session = None

# Global YouTube session manager
youtube_session_manager = YouTubeSessionManager()

@retry_on_youtube_error(max_retries=3, delay=1)
async def safe_youtube_request(func, *args, **kwargs):
    """Safe wrapper for YouTube operations with retry logic and connection pooling"""
    try:
        if NETWORK_UTILS_AVAILABLE:
            # Use network_utils if available
            return await safe_request(*args, **kwargs)
        else:
            # Fallback to direct request with session management
            session = await youtube_session_manager.get_session()
            return await func(session, *args, **kwargs)
    except Exception as e:
        error_msg = str(e).lower()
        if any(keyword in error_msg for keyword in ['connection', 'tls', 'reset', 'timeout']):
            # Reset session on connection error
            cogs_logger.warning(f"YouTube connection error, resetting session: {e}")
            await youtube_session_manager.close()
            await asyncio.sleep(2)
            
            # Retry with fresh session
            session = await youtube_session_manager.get_session()
            return await func(session, *args, **kwargs)
        raise e

# Optimized executor configuration
class OptimizedExecutor:
    def __init__(self, max_workers=2):  # Reduced from 4 to 2
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._shutdown = False
    
    async def run_in_thread(self, func, *args, **kwargs):
        """Run blocking function in thread with timeout"""
        if self._shutdown:
            raise RuntimeError("Executor is shutdown")
        
        loop = asyncio.get_event_loop()
        try:
            # Add timeout to prevent hanging
            return await asyncio.wait_for(
                loop.run_in_executor(self.executor, func, *args, **kwargs),
                timeout=10.0  # 10 second timeout
            )
        except asyncio.TimeoutError:
            cogs_logger.warning(f"Thread execution timeout for {func.__name__}")
            raise Exception("Operation timed out")
    
    def shutdown(self):
        self._shutdown = True
        self.executor.shutdown(wait=False)

@dataclass
class CachedSearchResult:
    """Cached search result with TTL"""
    result: Dict
    timestamp: float
    ttl: float = 300.0  # 5 minutes TTL

class OptimizedCache:
    """Memory-efficient cache with TTL and size limits"""
    
    def __init__(self, max_size: int = 30, ttl: float = 300.0):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: Dict[str, CachedSearchResult] = {}
        self._access_order = deque()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Dict]:
        async with self._lock:
            if key not in self._cache:
                return None
            
            result = self._cache[key]
            if time.time() - result.timestamp > result.ttl:
                # Expired, remove it
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                return None
            
            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return result.result
    
    async def set(self, key: str, value: Dict):
        async with self._lock:
            # Remove oldest if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                oldest_key = self._access_order.popleft()
                if oldest_key in self._cache:
                    del self._cache[oldest_key]
            
            # Add/update entry
            self._cache[key] = CachedSearchResult(value, time.time(), self.ttl)
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            
    async def cleanup_expired(self):
        """Remove expired entries"""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, result in self._cache.items()
                if current_time - result.timestamp > result.ttl
            ]
            for key in expired_keys:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)

class PerformanceMonitor:
    """Monitor and log performance metrics"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self._lock = asyncio.Lock()
    
    async def record_metric(self, name: str, value: float):
        async with self._lock:
            self.metrics[name].append(value)
            # Keep only last 100 measurements
            if len(self.metrics[name]) > 100:
                self.metrics[name] = self.metrics[name][-100:]
    
    async def get_average(self, name: str) -> float:
        async with self._lock:
            values = self.metrics.get(name, [])
            return sum(values) / len(values) if values else 0.0

# Rate limiter for API calls
class RateLimiter:
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = deque()
    
    async def acquire(self):
        now = time.time()
        # Remove old calls outside time window
        while self.calls and now - self.calls[0] > self.time_window:
            self.calls.popleft()
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.calls[0] + self.time_window - now
            if sleep_time > 0:
                cogs_logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                return await self.acquire()
        
        self.calls.append(now)

# Optimized YouTube operations with enhanced error handling
class OptimizedYouTubeOperations:
    """Optimized YouTube operations with caching, rate limiting, and retry logic"""
    
    @staticmethod
    async def search_videos(query: str, limit: int = 1) -> List[Dict]:
        """Cached video search with rate limiting and retry logic"""
        cache_key = f"search:{query}:{limit}"
        
        # Try cache first
        cached_result = await search_cache.get(cache_key)
        if cached_result:
            await performance_monitor.record_metric("cache_hit", 1.0)
            return cached_result
        
        # Rate limit and search with circuit breaker
        async def _search_impl():
            await search_rate_limiter.acquire()
            start_time = time.time()
            
            try:
                search = VideosSearch(query=query, limit=limit)
                results = search.result()['result']
                
                # Cache the result
                await search_cache.set(cache_key, results)
                
                await performance_monitor.record_metric("search_time", time.time() - start_time)
                await performance_monitor.record_metric("cache_hit", 0.0)
                
                return results
            except Exception as e:
                cogs_logger.error(f"YouTube search failed: {e}")
                raise
        
        try:
            return await youtube_circuit_breaker.call(_search_impl)
        except Exception as e:
            cogs_logger.error(f"YouTube search circuit breaker error: {e}")
            # Fallback: return empty results instead of crashing
            return []

    @staticmethod
    async def get_video_info(url: str) -> Dict:
        """Cached video info with rate limiting and retry logic"""
        cache_key = f"video_info:{url}"
        
        # Try cache first
        cached_result = await url_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Rate limit and get info with circuit breaker
        async def _video_info_impl():
            await api_rate_limiter.acquire()
            start_time = time.time()
            
            try:
                video_info = Video.getInfo(url, mode=ResultMode.json)
                await url_cache.set(cache_key, video_info)
                
                await performance_monitor.record_metric("video_info_time", time.time() - start_time)
                return video_info
            except Exception as e:
                cogs_logger.error(f"Video info fetch failed: {e}")
                raise
        
        try:
            return await youtube_circuit_breaker.call(_video_info_impl)
        except Exception as e:
            cogs_logger.error(f"Video info circuit breaker error: {e}")
            # Return minimal info to prevent cascading failures
            return {
                'title': 'Video unavailable',
                'channel': {'name': 'Unknown', 'id': '', 'url': ''},
                'thumbnails': [{'url': ''}],
                'duration': '0',
                'viewCount': {'text': '0'},
                'link': url
            }
        
    @staticmethod
    async def get_channel_info(channel_id: str) -> Dict:
        """Lightweight channel info with retry logic"""
        cache_key = f"channel_info:{channel_id}"
        
        # Try cache first
        cached_result = await url_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Rate limit and get info with circuit breaker
        async def _channel_info_impl():
            await api_rate_limiter.acquire()
            start_time = time.time()
            
            try:
                channel_info = Channel.get(channel_id)
                await url_cache.set(cache_key, channel_info)
                
                await performance_monitor.record_metric("channel_info_time", time.time() - start_time)
                return channel_info
            except Exception as e:
                cogs_logger.error(f"Channel info fetch failed: {e}")
                raise
        
        try:
            return await youtube_circuit_breaker.call(_channel_info_impl)
        except Exception as e:
            cogs_logger.error(f"Channel info circuit breaker error: {e}")
            # Return minimal info to prevent cascading failures
            return {
                'title': 'Unknown Channel',
                'thumbnails': [{'url': ''}],
                'url': f"https://www.youtube.com/channel/{channel_id}"
            }
        
# Optimized utility functions
def get_video_id_from_url(url: str) -> str:
    """Extract YouTube video ID from URL - optimized version"""
    try:
        if not isinstance(url, str):
            return ''
        patterns = [
            r"v=([A-Za-z0-9_-]{11})",
            r"youtu\.be/([A-Za-z0-9_-]{11})",
            r"/embed/([A-Za-z0-9_-]{11})",
            r"([A-Za-z0-9_-]{11})$"
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
    except Exception:
        return ''
    return ''

def normalize_youtube_link(link: str) -> str:
    """Normalize YouTube URL - optimized version"""
    try:
        if not isinstance(link, str):
            return link
        video_id = get_video_id_from_url(link)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        pass
    return link

def format_duration(seconds_or_str) -> str:
    """Convert duration to MM:SS format - optimized"""
    try:
        if isinstance(seconds_or_str, str) and ':' in seconds_or_str:
            return seconds_or_str
        seconds = int(seconds_or_str)
        return f"{seconds//60:02d}:{seconds%60:02d}"
    except (ValueError, TypeError):
        return str(seconds_or_str)

def format_view_count(count_or_str) -> str:
    """Format view count - optimized"""
    try:
        if isinstance(count_or_str, str) and any(c in count_or_str for c in ['K', 'M', 'B']):
            return count_or_str
        count = int(str(count_or_str).replace(',', ''))
        if count >= 1_000_000_000:
            return f"{count/1_000_000_000:.1f}B"
        elif count >= 1_000_000:
            return f"{count/1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count/1_000:.1f}K"
        return str(count)
    except (ValueError, TypeError):
        return str(count_or_str)

# Optimized audio extraction
async def get_audio_source_optimized(song_url: str) -> str:
    """Optimized audio source extraction with timeout and retry"""
    headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    }
    
    ydl_opts = {
        'format': 'bestaudio[acodec^=opus]/bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
        'headers': headers,
        'socket_timeout': 10,  # Add timeout
    }

    def extract():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(song_url, download=False)
                return info['url']
        except Exception as e:
            cogs_logger.error(f"yt_dlp extraction failed: {e}")
            raise

    max_retries = 2  # Reduced from 3
    for attempt in range(max_retries):
        try:
            audio_url = await executor.run_in_thread(extract)
            await performance_monitor.record_metric("audio_extraction_time", time.time())
            return audio_url
        except Exception as e:
            if attempt < max_retries - 1:
                cogs_logger.warning(f"Audio extraction attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(1)
                continue
            else:
                cogs_logger.error(f"Audio extraction failed after {max_retries} attempts: {e}")
                raise Exception(f"Failed to extract audio URL: {str(e)}")
    
    raise Exception("Failed to get audio URL")

# Memory-efficient guild data management
class GuildDataManager:
    """Manages guild-specific data with automatic cleanup"""
    
    def __init__(self):
        self.queues: Dict[int, List[Dict]] = {}
        self.current_songs: Dict[int, Dict] = {}
        self.autoplay: Dict[int, bool] = {}
        self.recent_played: Dict[int, List[Dict]] = {}
        self.disconnect_tasks: Dict[int, asyncio.Task] = {}
        self._weak_refs = weakref.WeakSet()
        # Add queue locks to prevent race conditions
        self._queue_locks = defaultdict(asyncio.Lock)
        self._last_access_time: Dict[int, float] = {}
    
    def get_queue(self, guild_id: int) -> List[Dict]:
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        # Update last access time for better cleanup decisions
        self._last_access_time[guild_id] = time.time()
        return self.queues[guild_id]
    
    async def safe_queue_append(self, guild_id: int, song_data: Dict):
        """Thread-safe queue append operation"""
        async with self._queue_locks[guild_id]:
            queue = self.get_queue(guild_id)
            queue.append(song_data)
            self._last_access_time[guild_id] = time.time()
            cogs_logger.debug(f"Added song to queue for guild {guild_id}: {song_data['title']}")
    
    async def safe_queue_pop(self, guild_id: int) -> Optional[Dict]:
        """Thread-safe queue pop operation"""
        async with self._queue_locks[guild_id]:
            queue = self.get_queue(guild_id)
            if queue:
                song = queue.pop(0)
                self._last_access_time[guild_id] = time.time()
                cogs_logger.debug(f"Removed song from queue for guild {guild_id}: {song['title']}")
                return song
            return None
    
    async def safe_queue_remove(self, guild_id: int, index: int) -> Optional[Dict]:
        """Thread-safe queue remove by index operation"""
        async with self._queue_locks[guild_id]:
            queue = self.get_queue(guild_id)
            if 0 <= index < len(queue):
                song = queue.pop(index)
                self._last_access_time[guild_id] = time.time()
                cogs_logger.debug(f"Removed song at index {index} from queue for guild {guild_id}: {song['title']}")
                return song
            return None
    
    async def safe_queue_clear(self, guild_id: int):
        """Thread-safe queue clear operation"""
        async with self._queue_locks[guild_id]:
            if guild_id in self.queues:
                cleared_count = len(self.queues[guild_id])
                self.queues[guild_id].clear()
                self._last_access_time[guild_id] = time.time()
                cogs_logger.info(f"Cleared {cleared_count} songs from queue for guild {guild_id}")
    
    def should_cleanup_guild(self, guild_id: int) -> bool:
        """Check if a guild should be cleaned up based on activity"""
        current_time = time.time()
        last_access = self._last_access_time.get(guild_id, 0)
        
        # Only cleanup if:
        # 1. No queue activity for 30+ minutes
        # 2. No current song playing
        # 3. No autoplay enabled
        time_since_access = current_time - last_access
        
        return (time_since_access > 1800 and  # 30 minutes
                guild_id not in self.current_songs and
                not self.autoplay.get(guild_id, False))
    
    async def cleanup_guild_data(self, guild_id: int):
        """Clean up data for a specific guild"""
        try:
            self.queues.pop(guild_id, None)
            self.current_songs.pop(guild_id, None)
            self.autoplay.pop(guild_id, None)
            self.recent_played.pop(guild_id, None)
            
            # Cancel disconnect task if exists
            if guild_id in self.disconnect_tasks:
                task = self.disconnect_tasks.pop(guild_id)
                if not task.done():
                    task.cancel()
        except Exception as e:
            cogs_logger.error(f"Error cleaning up guild {guild_id}: {e}")

    async def cleanup_all_expired(self):
        """Background cleanup task"""
        while True:
            try:
                # Clean expired cache entries
                await search_cache.cleanup_expired()
                await url_cache.cleanup_expired()
                
                # Clean old guild data using intelligent cleanup logic
                guilds_to_clean = []
                for guild_id in list(self.queues.keys()):
                    if self.should_cleanup_guild(guild_id):
                        guilds_to_clean.append(guild_id)
                
                if guilds_to_clean:
                    cogs_logger.info(f"Cleaning up {len(guilds_to_clean)} inactive guilds: {guilds_to_clean}")
                
                for guild_id in guilds_to_clean:
                    await self.cleanup_guild_data(guild_id)
                
                # Log performance metrics
                avg_search_time = await performance_monitor.get_average("search_time")
                if avg_search_time > 2.0:
                    cogs_logger.warning(f"Slow search detected: {avg_search_time:.2f}s average")
                
                await asyncio.sleep(300)  # Run every 5 minutes
            except Exception as e:
                cogs_logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)  # Wait longer on error

class SongRemovalSelect(discord.ui.Select):
    """Custom select component for song removal"""
    
    def __init__(self, queue, cog):
        self.queue = queue
        self.cog = cog
        
        # Generate options dynamically based on current queue state
        options = [
            discord.SelectOption(
                label=f"{i+1}. {song['title'][:50]}{'...' if len(song['title']) > 50 else ''}",
                value=str(i),
                description=f"Duration: {song.get('duration', 'Unknown')}"
            ) for i, song in enumerate(queue[:25])  # Limit to 25 songs
        ]
        
        super().__init__(
            placeholder="Choose a song to remove...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle song selection and removal"""
        try:
            song_index = int(self.values[0])
            
            # Remove song from queue
            if 0 <= song_index < len(self.queue):
                removed_song = self.queue.pop(song_index)
                await interaction.response.send_message(
                    f"✅ Removed: {removed_song['title']}", 
                    ephemeral=True, 
                    delete_after=5
                )
            else:
                await interaction.response.send_message(
                    "❌ Invalid song selection.", 
                    ephemeral=True
                )
        except Exception as e:
            cogs_logger.error(f"Error in song removal: {e}")
            await interaction.response.send_message(
                "❌ Error removing song.", 
                ephemeral=True
            )


class SongRemovalView(discord.ui.View):
    """View for selecting and removing a specific song from queue"""
    
    def __init__(self, queue, cog, timeout=60):
        super().__init__(timeout=timeout)
        self.queue = queue
        self.cog = cog
        
        # Add the select component
        self.add_item(SongRemovalSelect(queue, cog))
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel song removal"""
        try:
            await interaction.response.send_message("❌ Cancelled song removal.", ephemeral=True, delete_after=3)
        except Exception as e:
            cogs_logger.error(f"Error in cancel button: {e}")
            await interaction.response.send_message("❌ Error cancelling.", ephemeral=True)

class MusicControls(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
        
    @discord.ui.button(label="⏸", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel", ephemeral=True)
            return
        
        try:
            voice_client = interaction.guild.voice_client
            if voice_client.is_playing():
                voice_client.pause()
                button.disabled = True
                self.resume_button.disabled = False
                await interaction.response.edit_message(view=self)
                await interaction.followup.send("Paused!", ephemeral=True)
            else:
                await interaction.followup.send("Nothing is playing", ephemeral=True)
        except Exception as e:
            cogs_logger.warning(f"Failed in pause_button: {e}")

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, disabled=True)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel", ephemeral=True)
            return
        
        try:
            voice_client = interaction.guild.voice_client
            if voice_client.is_paused():
                voice_client.resume()
                button.disabled = True
                self.pause_button.disabled = False
                await interaction.response.edit_message(view=self)
                await interaction.followup.send("Resumed!", ephemeral=True)
            else:
                await interaction.followup.send("Not paused", ephemeral=True)
        except Exception as e:
            cogs_logger.warning(f"Failed in resume_button: {e}")

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        try:
            voice_client = interaction.guild.voice_client
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
                await interaction.response.send_message("Skipped!", ephemeral=True, delete_after=5)
            else:
                await interaction.response.send_message("Nothing is playing to skip!", ephemeral=True)
        except Exception as e:
            cogs_logger.warning(f"Failed in skip_button: {e}")

    @discord.ui.button(label="⏹", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        try:
            await guild_data.cleanup_guild_data(guild_id)
            voice_client = interaction.guild.voice_client
            voice_client.stop()
            
            # Update button states
            for child in self.children:
                child.disabled = True
            
            await interaction.response.edit_message(view=self)
            await interaction.response.send_message("Stopped!", ephemeral=True, delete_after=5)
            
            # Remove bot status
            try:
                await self.cog.bot.change_presence(activity=discord.Game(name="Hide and Seek", platform="Closet"))
            except Exception as e:
                cogs_logger.warning(f"Failed to remove bot status: {e}")
                
        except Exception as e:
            cogs_logger.warning(f"Failed in stop_button: {e}")

    @discord.ui.button(label="Autoplay: 🔴", style=discord.ButtonStyle.secondary)
    async def autoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle autoplay + auto-start music if queue is empty"""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("This only works in servers!", ephemeral=True)
            return

        voice_client = guild.voice_client
        if not voice_client:
            await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)
            return

        gid = guild.id
        was_enabled = guild_data.autoplay.get(gid, False)
        now_enabled = not was_enabled
        guild_data.autoplay[gid] = now_enabled

        # Update button appearance
        button.label = f"Autoplay: {'🟢' if now_enabled else '🔴'}"
        button.style = discord.ButtonStyle.success if now_enabled else discord.ButtonStyle.secondary

        await interaction.response.edit_message(view=self)
        
        # ———————— NEW: AUTO-START MUSIC WHEN TURNING ON ————————
        if now_enabled and not was_enabled:  # Was off → now on
            if len(guild_data.get_queue(gid)) == 0:  # Queue is empty → let's fill it!
                # Create a context-like object for the bot
                ctx = await self.cog.bot.get_context(interaction.message)

                # Try to base it on the last played song
                recent = guild_data.recent_played.get(gid, [])
                if recent:
                    last_song = recent[-1]
                    title = last_song.get('title', 'music')
                    await interaction.followup.send("Autoplay enabled! Starting radio based on your last song...", ephemeral=True)
                else:
                    title = "lofi hip hop radio beats to relax/study to"  # Classic fallback
                    await interaction.followup.send("Autoplay enabled! Starting a chill radio...", ephemeral=True)

                # Add 3 songs to queue using real YouTube recommendations
                added = await self.cog.add_autoplay_suggestions(ctx, gid, count=3)

                if added > 0 and not voice_client.is_playing():
                    # Force play the next song immediately
                    try:
                        await self.cog.play_next_optimized(ctx)
                    except:
                        pass  # play_next will handle errors

    @discord.ui.button(label="☰ Show Queue", style=discord.ButtonStyle.secondary)
    async def show_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show the current music queue."""
        queue = guild_data.get_queue(interaction.guild.id)
        
        if not queue:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return
        
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue[:10]))
        
        if len(queue) > 10:
            queue_list += f"\n... and {len(queue) - 10} more song(s)"
        
        await interaction.response.send_message(f"**Current Queue:**\n{queue_list}")
        
    @discord.ui.button(label="🗑️ Clear Queue", style=discord.ButtonStyle.danger)
    async def clear_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear the current music queue."""
        guild_id = interaction.guild.id
        await guild_data.safe_queue_clear(guild_id)
        await interaction.response.send_message("Cleared the music queue.", ephemeral=True, delete_after=4)

    @discord.ui.button(label="❌ Remove Song", style=discord.ButtonStyle.secondary)
    async def remove_song_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove a specific song from the queue."""
        guild_id = interaction.guild.id
        queue = guild_data.get_queue(guild_id)
        
        if not queue:
            await interaction.response.send_message("The queue is empty.", ephemeral=True, delete_after=4)
            return
        
        # Create view for song selection
        removal_view = SongRemovalView(queue, self.cog)
        await interaction.response.send_message(
            "Select a song to remove from the queue:",
            view=removal_view,
            ephemeral=True
        )

    @discord.ui.button(label="📝 Lyrics", style=discord.ButtonStyle.secondary)
    async def lyrics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Fetch and display lyrics for the currently playing song."""
        from controllers.lyrics_fetcher import fetch_song_lyrics, is_genius_available
        
        if not is_genius_available():
            await interaction.response.send_message(
                "❌ Lyrics feature is not available. The bot owner needs to configure the Genius API token.",
                ephemeral=True,
                delete_after=4
            )
            return
        
        guild_id = interaction.guild.id
        if guild_id not in guild_data.current_songs:
            await interaction.response.send_message("No song is currently playing!", ephemeral=True)
            return
        
        try : 
            tempmsg = await interaction.response.send_message(
                "🎵 Searching for lyrics...",
                ephemeral=True, delete_after=60
            )
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
            
        try:
            song = guild_data.current_songs[guild_id]

            song_title = song.get('title', '')
            artist_name = song.get('channel_name', '')

            result = await fetch_song_lyrics(song_title, artist_name)
            
            if not result.get('success'):
                await interaction.followup.send(f"❌ {result.get('error', 'Could not fetch lyrics')}", ephemeral=True)
                return
            
            try :
                await interaction.delete_original_response()
            except Exception:
                pass
            
            embed = discord.Embed(
                title=result['title'],
                description=result['artist'],
                url=result['url'],
                color=discord.Color.gold()
            )
            
            lyrics_text = result['lyrics']
            
            # Split lyrics into chunks to fit multiple fields
            if len(lyrics_text) <= character_chunk.MAX_FIELD_LENGTH:
                embed.add_field(name="Lyrics", value=lyrics_text, inline=False)
            else:               
                chunks = character_chunk.get_chunk(lyrics_text)
                
                for i, chunk in enumerate(chunks):
                    field_name = "Lyrics" if i == 0 else f"Lyrics (cont.)"
                    embed.add_field(name=field_name, value=chunk, inline=False)
            
            embed.set_footer(text="Powered by Genius")
            
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                message_content = f"**{result['title']}** by {result['artist']}\n\n{lyrics_text}\n\n[Full lyrics on Genius]({result['url']})"
            
                if len(message_content) <= 2000:
                    await interaction.followup.send(message_content, ephemeral=True)
                else:
                    chunks = [message_content[i:i+1900] for i in range(0, len(message_content), 1900)]
                    for chunk in chunks:
                        await interaction.followup.send(chunk, ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching lyrics: {str(e)}", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cleanup_task = None
        
    async def cog_load(self):
        """Start background cleanup task when cog loads"""
        self._cleanup_task = asyncio.create_task(guild_data.cleanup_all_expired())
        cogs_logger.info("Music cog loaded with cleanup task")
        
    async def cog_unload(self):
        """Cleanup when cog unloads"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        executor.shutdown()
        cogs_logger.info("Music cog unloaded")
        
    async def play_music_optimized(self, ctx: commands.Context, query: str):
        """Optimized music playing with reduced API calls"""
        try:
            guild_id = ctx.guild.id
            queue = guild_data.get_queue(guild_id)
            
            if len(queue) >= 10:
                await ctx.send("Queue is full! Max 10 songs.")
                return
            
            if not ctx.author.voice:
                await ctx.send('You need to join a voice channel first!')
                return

            # Connect to voice if not already connected
            if not ctx.voice_client:
                channel = ctx.author.voice.channel
                await channel.connect()
                await ctx.send(f'Joined {channel.name}')
            
            voice_client = ctx.voice_client
            
            # Search for video (cached)
            start_time = time.time()
            results = await OptimizedYouTubeOperations.search_videos(query, limit=1)
            
            if not results:
                await ctx.send(f'No music found for {query}')
                return
            
            video = results[0]
            
            # Get video info (cached)
            video_info = await OptimizedYouTubeOperations.get_video_info(video['link'])
            
            # Get channel info (cached) - only if needed
            channel_info = {}
            try:
                channel_info = await OptimizedYouTubeOperations.get_channel_info(video['channel']['id'])
            except Exception:
                # Fallback to basic channel info from search result
                channel_info = {
                    'title': video['channel']['name'],
                    'thumbnails': [{'url': video['channel'].get('thumbnails', [{}])[0].get('url', '')}],
                    'url': video['channel'].get('url', f"https://www.youtube.com/channel/{video['channel']['id']}")
                }
            
            # Build song data with minimal processing
            song_data = {
                'url': video['link'],
                'video_id': get_video_id_from_url(video['link']) or '',
                'title': video['title'],
                'thumbnail': video['thumbnails'][0]['url'],
                'channel_name': channel_info.get('title', video['channel']['name']),
                'channel_id': video['channel']['id'],
                'channel_thumbnails': channel_info.get('thumbnails', [{}])[0].get('url', ''),
                'channel_url': channel_info.get('url', ''),
                'duration': format_duration(video.get('duration', '0')),
                'view_count': format_view_count(video.get('viewCount', {}).get('short', '0'))
            }
            
            await guild_data.safe_queue_append(guild_id, song_data)
            
            search_time = time.time() - start_time
            await performance_monitor.record_metric("total_search_time", search_time)
            
            if not voice_client.is_playing():
                await self.play_next_optimized(ctx)
            else:
                await ctx.send(f"Added to queue: {song_data['title']}")
                
        except Exception as e:
            cogs_logger.error(f"Error in play_music_optimized: {e}")
            await ctx.send(f"Something went wrong: {str(e)}")
            
    async def play_next_optimized(self, ctx: commands.Context):
        """Optimized play_next with better error handling"""
        try:
            if not ctx.voice_client:
                return
            
            voice_client = ctx.voice_client
            guild_id = ctx.guild.id
            queue = guild_data.get_queue(guild_id)
            
            if not queue:
                await ctx.send("Queue is empty!", ephemeral=True, delete_after=5)
                try:
                    await self.bot.change_presence(activity=discord.Game(name="Hide and seek", platform="Closet"))
                except Exception:
                    pass
                return
            
            song = await guild_data.safe_queue_pop(guild_id)
            if not song:
                return
            guild_data.current_songs[guild_id] = song
            
            # Create simple embed (optimized)
            try:
                embed = discord.Embed(title=f"Now Playing: {song['title']}")
                embed.set_author(name=song['channel_name'], url=song.get('channel_url', ''))
                embed.set_thumbnail(url='https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png')
                embed.add_field(name="Duration", value=song.get('duration', 'Unknown'), inline=True)
                embed.add_field(name="Views", value=song.get('view_count', 'Unknown'), inline=True)
                if song.get('thumbnail'):
                    embed.set_image(url=song['thumbnail'])
                
                # Create view
                view = MusicControls(self)
                autoplay_enabled = guild_data.autoplay.get(guild_id, False)
                view.autoplay_button.label = f"Autoplay: {'🟢' if autoplay_enabled else '🔴'}"
                view.autoplay_button.style = discord.ButtonStyle.success if autoplay_enabled else discord.ButtonStyle.secondary
                
                # Simple status update (throttled)
                try:
                    activity = discord.Activity(
                        type=discord.ActivityType.listening,
                        name=f"🎵 {song['title'][:30]}..."
                    )
                    await self.bot.change_presence(activity=activity)
                except Exception:
                    pass
                
                await ctx.send(embed=embed, view=view)
                
            except Exception as e:
                cogs_logger.warning(f"Failed to send embed: {e}")
            
            # Play audio with optimized extraction
            try:
                audio_url = await get_audio_source_optimized(song['url'])
            except Exception as e:
                await ctx.send(f"Failed to get audio stream: {str(e)}")
                # Clean up and try next song
                guild_data.current_songs.pop(guild_id, None)
                if queue:
                    await self.play_next_optimized(ctx)
                return
            
            # Optimized FFmpeg options
            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1',
                'options': '-b:a 64k'  # Lower bitrate for less CPU usage
            }
            
            def custom_probe(source, executable):
                return 'opus', '64k'
            
            source = await discord.FFmpegOpusAudio.from_probe(
                audio_url,
                method=custom_probe,
                executable='ffmpeg',
                **ffmpeg_options
            )
            
            def after_playing(error):
                if error:
                    cogs_logger.error(f"Playback error: {error}")
                # Schedule next song
                coroutine = self.play_next_optimized(ctx)
                future = asyncio.run_coroutine_threadsafe(coroutine, loop=self.bot.loop)
                
                try:
                    future.result()
                except Exception as e:
                    cogs_logger.error(f"Error in after_playing : {e}")
            
            voice_client.play(source, after=after_playing)
            
            # Update recent played (limited size)
            recent = guild_data.recent_played.get(guild_id, [])
            recent.append({
                'id': song.get('video_id', ''),
                'title': song['title'],
                'channel_name': song.get('channel_name', '')
            })
            guild_data.recent_played[guild_id] = recent[-10:]  # Keep only last 10
            
            if guild_data.autoplay.get(guild_id, False) and len(queue) < 3:
                await self.add_autoplay_suggestions(ctx, guild_id, count=3)
            
        except Exception as e:
            cogs_logger.error(f"Error in play_next_optimized: {e}")
            await ctx.send(f"Playback error: {str(e)}")
            
    @commands.hybrid_command(name="play")
    @app_commands.describe(
        query="Song title to search on YouTube",
        link="YouTube video link (youtu.be or youtube.com format)"
    )
    async def play(self, ctx: commands.Context, query: str = None, link: str = None):
        """Play a song by query or YouTube link. Prioritizes query if both are provided."""
        try:
            try:
                await ctx.defer()
            except Exception:
                pass
            if query:
                try :
                    await self.play_music_optimized(ctx, query)
                except Exception as e:
                    await ctx.send(f"Something went wrong: {e}")
            elif link:
                try :
                    await self.play_music_by_url_optimized(ctx, link)
                except Exception as e:
                    await ctx.send(f"Something went wrong: {e}")
            else:
                await ctx.send("Please provide either a song name (query) or a YouTube link.")
        except Exception as e:
            await ctx.send(f"Something went wrong: {e}")

    async def play_music_by_url_optimized(self, ctx: commands.Context, link: str):
        """Optimized music playing by URL with reduced API calls"""
        try:
            guild_id = ctx.guild.id
            queue = guild_data.get_queue(guild_id)
            
            if len(queue) >= 10:
                await ctx.send("Queue is full! Max 10 songs.")
                return
            
            if not ctx.author.voice:
                await ctx.send('You need to join a voice channel first!')
                return

            # Connect to voice if not already connected
            if not ctx.voice_client:
                channel = ctx.author.voice.channel
                await channel.connect()
                await ctx.send(f'Joined {channel.name}')
            
            voice_client = ctx.voice_client
            
            # Normalize and cache the URL
            normalized_link = normalize_youtube_link(link)
            
            # Get video info (cached)
            start_time = time.time()
            video_info = await OptimizedYouTubeOperations.get_video_info(normalized_link)
            
            if not video_info:
                await ctx.send(f'No music found for {link}')
                return
            
            # Get channel info (cached)
            channel_info = await OptimizedYouTubeOperations.get_channel_info(video_info['channel']['id'])
            
            # Build song data with minimal processing
            song_data = {
                'url': video_info['link'],
                'video_id': get_video_id_from_url(video_info['link']) or '',
                'title': video_info['title'],
                'thumbnail': video_info['thumbnails'][0]['url'],
                'channel_name': channel_info.get('title', video_info['channel']['name']),
                'channel_id': video_info['channel']['id'],
                'channel_thumbnails': channel_info.get('thumbnails', [{}])[0].get('url', ''),
                'channel_url': channel_info.get('url', ''),
                'duration': format_duration(video_info.get('duration', '0')),
                'view_count': format_view_count(video_info['viewCount']['text'])
            }
            
            await guild_data.safe_queue_append(guild_id, song_data)
            
            search_time = time.time() - start_time
            await performance_monitor.record_metric("url_search_time", search_time)
            
            if not voice_client.is_playing():
                await self.play_next_optimized(ctx)
            else:
                await ctx.send(f"Added to queue: {song_data['title']}")
                
        except Exception as e:
            cogs_logger.error(f"Error in play_music_by_url_optimized: {e}")
            await ctx.send(f"Something went wrong: {str(e)}")

    async def add_autoplay_suggestions(self, ctx: commands.Context, guild_id: int, count: int = 1):
        """Use yt_dlp to get REAL YouTube 'Up Next' / related videos for true autoplay"""
        try:
            """Fetch REAL YouTube autoplay recommendations safely in a thread"""
            if not ctx.guild or not ctx.voice_client:
                return 0

            recent = guild_data.recent_played.get(guild_id, [])
            if not recent:
                return 0

            last_song = recent[-1]
            video_id = last_song.get('id') or get_video_id_from_url(last_song.get('url', ''))
            if not video_id:
                return 0

            # Collect IDs to avoid duplicates
            played_ids = {item.get('id') for item in recent if item.get('id')}
            queued_ids = {song.get('video_id') for song in guild_data.get_queue(guild_id) if song.get('video_id')}
            avoid_ids = played_ids.union(queued_ids)

            def fetch_related():
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': True,
                    'skip_download': True,
                    'playlistend': count + 10,  # Get extra to filter
                }
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(
                            f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}",
                            download=False
                        )
                        return info.get('entries', [])[1:]  # Skip first (current song)
                except Exception as e:
                    cogs_logger.warning(f"[Autoplay] yt_dlp failed: {e}")
                    return []

            try:
                entries = await executor.run_in_thread(fetch_related)
            except Exception as e:
                cogs_logger.warning(f"[Autoplay] Thread execution failed: {e}")
                return 0

            added = 0
            seen = set()

            for entry in entries:
                if added >= count:
                    break

                vid_id = entry.get('id')
                if not vid_id or vid_id in avoid_ids or vid_id in seen:
                    continue
                if entry.get('title') in ('[Private video]', '[Deleted video]'):
                    continue

                title = entry.get('title', 'Unknown')
                url = f"https://www.youtube.com/watch?v={vid_id}"
                duration = format_duration(entry.get('duration')) if entry.get('duration') else "LIVE"
                thumbnail = entry['thumbnails'][-1]['url'] if entry.get('thumbnails') else ''

                channel_name = entry.get('uploader', 'Unknown')
                channel_id = entry.get('channel_id')

                channel_thumbnails = ''
                channel_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id else ''

                # Optional: enrich channel name (lightweight, async-safe)
                if channel_id:
                    try:
                        ch_info = await OptimizedYouTubeOperations.get_channel_info(channel_id)
                        channel_name = ch_info.get('title', channel_name)
                        if ch_info.get('thumbnails'):
                            channel_thumbnails = ch_info['thumbnails'][0]['url']
                        channel_url = ch_info.get('url', channel_url)
                    except Exception:
                        pass

                await guild_data.safe_queue_append(guild_id, {
                    'url': url, 
                    'video_id': vid_id, 
                    'title': title, 
                    'thumbnail': thumbnail, 
                    'channel_name': channel_name, 
                    'channel_id': channel_id or '', 
                    'duration': duration, 
                    'view_count': '', 
                    'channel_thumbnails': channel_thumbnails, 
                    'channel_url': channel_url
                })

                seen.add(vid_id)
                added += 1

            if added > 0:
                try:
                    await ctx.send(f"Autoplay added {added} new song(s)", delete_after=5)
                except Exception:
                    pass

            return added

        except Exception as e:
            cogs_logger.error(f"Autoplay error: {e}")
            return 0
            
    @commands.hybrid_command()
    async def stop(self, ctx: commands.Context):
        """Stop playing and cleanup"""
        if ctx.voice_client:
            guild_id = ctx.guild.id
            await guild_data.cleanup_guild_data(guild_id)
            ctx.voice_client.stop()
            
            try:
                await self.bot.change_presence(activity=discord.Game(name="Hide and seek", platform="Closet"))
            except Exception:
                pass
            
            await ctx.send("Stopped")
        else:
            await ctx.send("Nothing to stop")
    
    @commands.hybrid_command()
    async def skip(self, ctx: commands.Context):
        """Skip current song"""
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Skipped")
        else:
            await ctx.send("Nothing playing to skip!")
            
    @commands.hybrid_command()
    async def show_queue(self, ctx: commands.Context):
        """Show current queue"""
        guild_id = ctx.guild.id
        queue = guild_data.get_queue(guild_id)
        
        if not queue:
            await ctx.send("The queue is empty.")
            return
        
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue[:10]))
        if len(queue) > 10:
            queue_list += f"\n... and {len(queue) - 10} more"
        
        await ctx.send(f"**Current Queue:**\n{queue_list}")     
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before, after):
        """Optimized voice state update with improved cleanup logic"""
        try:
            if member == self.bot.user:
                # Only cleanup if bot completely disconnected (not when moving channels)
                if before.channel and not after.channel:
                    guild_id = member.guild.id
                    cogs_logger.info(f"Bot disconnected from guild {guild_id}, cleaning up data")
                    await guild_data.cleanup_guild_data(guild_id)
                return
            
            voice_client = member.guild.voice_client
            if not voice_client:
                return
            
            # Improved disconnect logic - only cleanup if truly alone
            if len(voice_client.channel.members) == 1:  # Only bot
                guild_id = member.guild.id
                if guild_id not in guild_data.disconnect_tasks:
                    task = asyncio.create_task(self._disconnect_timer(member.guild))
                    guild_data.disconnect_tasks[guild_id] = task
                    cogs_logger.debug(f"Started disconnect timer for guild {guild_id}")
            else:
                # Cancel disconnect task if users join
                guild_id = member.guild.id
                if guild_id in guild_data.disconnect_tasks:
                    guild_data.disconnect_tasks[guild_id].cancel()
                    del guild_data.disconnect_tasks[guild_id]
                    cogs_logger.debug(f"Cancelled disconnect timer for guild {guild_id}")
        except Exception as e:
            cogs_logger.error(f"Error in voice state update: {e}")
            
    async def _disconnect_timer(self, guild: discord.Guild):
        """Disconnect after 5 minutes of inactivity"""
        await asyncio.sleep(300)  # 5 minutes
        try:
            voice_client = guild.voice_client
            if voice_client and len(voice_client.channel.members) == 1:
                await voice_client.disconnect(force=True)
                guild.voice_client = None
        except Exception as e:
            cogs_logger.error(f"Error during disconnect: {e}")
        finally:
            guild_id = guild.id
            await guild_data.cleanup_guild_data(guild_id)
            guild_data.disconnect_tasks.pop(guild_id, None)      
    
    @commands.hybrid_command() # TODO : Modify/Optimize
    async def arise(self, ctx : commands.Context):            
        """Join the voice channel"""
        if not ctx.author.voice:
            await ctx.send("You are not in a voice channel!")
            return

        channel = ctx.author.voice.channel
        
        try:
            await ctx.defer()
        except Exception:
            pass

        try:
            if ctx.voice_client is not None:
                # NEW: Handle zombie state
                if not ctx.voice_client.is_connected():
                    await ctx.voice_client.disconnect(force=True)
                    ctx.guild.voice_client = None  # Clear zombie

                if ctx.voice_client is not None:  # Re-check after cleanup
                    if ctx.voice_client.channel == channel:
                        await ctx.send("Already in your voice channel!")
                        return
                    else:
                        await ctx.voice_client.move_to(channel)
                        await ctx.send(f"Moved to {channel}")
                        return
        except Exception as e:
            await ctx.send(f"Error handling existing voice client: {e}", ephemeral=True)
            return

        await channel.connect()
        await ctx.send(f"I've been summoned to {channel.name}")
            
    @commands.hybrid_command() # TODO : Modify/Optimize
    async def release(self, ctx : commands.Context):
        """ Leave a voice Channel """
        guild_id = ctx.guild.id
        if ctx.voice_client:
            await guild_data.safe_queue_clear(guild_id)
            self.channel = None
            
            try:
                await self.bot.change_presence(activity=discord.Game(name="Hide and seek", platform="Closet"))
                # await self.bot.change_presence(activity=discord.Activity(state=discord.ActivityType.playing, name="Your Mom"))
            except Exception as e:
                print(f"Error removing bot status: {e}")
                pass
            
            try:
                if guild_id in guild_data.current_songs:
                    del guild_data.current_songs[guild_id]

                await ctx.voice_client.disconnect(force=True)
                try:
                    ctx.guild.voice_client = None
                except Exception:
                    pass
                
                if ctx.guild.id in guild_data.disconnect_tasks:
                    del guild_data.disconnect_tasks[ctx.guild.id]
            except Exception as e:
                await ctx.send(f"Error disconnecting: {e}", ephemeral=True)
                pass
                
            await ctx.send('kbay')
        else:
            await ctx.send("I'm not in a voice channel")
      
    @commands.hybrid_command() # TODO : Optimize if can
    async def lyrics(self, ctx: commands.Context, *, song_query: str = None):
        """Fetch and display lyrics for a song.
        
        Usage:
        - /lyrics [song name and artist] - Fetch lyrics for a specific song
        - /lyrics - Fetch lyrics for the currently playing song
        """
        if not is_genius_available():
            await ctx.send(
                "❌ Lyrics feature is not available. The bot owner needs to set the `GENIUS_API_TOKEN` environment variable.\n"
                "Get a free token from: https://genius.com/api-clients"
            )
            return
        
        guild_id = ctx.guild.id
        
        if not song_query:
            q = guild_data.get_queue(guild_id)
            if not q and guild_id not in guild_data.current_songs:
                await ctx.send("Please provide a song name, or play a song first.")
                return
            if guild_id in guild_data.current_songs:
                song_query = guild_data.current_songs[guild_id].get('title', '')
            else:
                await ctx.send("Please provide a song name, or play a song first.")
                return
        
        try:
            await ctx.defer()
        except Exception:
            pass
        
        try:
            await ctx.send(f"🎵 Searching for lyrics for **{song_query}**...")
            
            result = await fetch_song_lyrics(song_query)
            
            if not result.get('success'):
                await ctx.send(f"❌ {result.get('error', 'Could not fetch lyrics')}")
                return
            
            embed = discord.Embed(
                title=result['title'],
                description=result['artist'],
                url=result['url'],
                color=discord.Color.gold()
            )
            
            lyrics_text = result['lyrics']
            
            if len(lyrics_text) <= character_chunk.MAX_FIELD_LENGTH:
                embed.add_field(name="Lyrics", value=lyrics_text, inline=False)
            else:                    
                chunks = character_chunk.get_chunk(lyrics_text)
                
                for i, chunk in enumerate(chunks):
                    field_name = "Lyrics" if i == 0 else f"Lyrics (cont.)"
                    embed.add_field(name=field_name, value=chunk, inline=False)
            
            embed.set_footer(text="Powered by Genius")
            
            try:
                await ctx.send(embed=embed)
            except Exception as e:
                message_content = f"**{result['title']}** by {result['artist']}\n\n{lyrics_text}\n\n[Full lyrics on Genius]({result['url']})"
                if len(message_content) <= 2000:
                    await ctx.send(message_content)
                else:
                    chunks = [message_content[i:i+1900] for i in range(0, len(message_content), 1900)]
                    for chunk in chunks:
                        await ctx.send(chunk)
        
        except Exception as e:
            await ctx.send(f"❌ Error fetching lyrics: {str(e)}")
    
    @commands.hybrid_command()
    async def clear_queue(self, ctx: commands.Context):
        """Clear current queue"""
        guild_id = ctx.guild.id
        await guild_data.safe_queue_clear(guild_id)
        await ctx.send(f"Queue cleared by {ctx.author.mention}")
        
    @commands.hybrid_command()
    async def remove(self, ctx: commands.Context, index: int):
        """Remove song at specified index"""
        guild_id = ctx.guild.id
        q = guild_data.get_queue(guild_id)
        if not q:
            await ctx.send("The queue is empty.")
            return
        
        index = index - 1
        if index < 0 or index >= len(q):
            await ctx.send(f"Invalid index. Use a number between 1 and {len(q)}.")
            return
        
        removed_song = await guild_data.safe_queue_remove(guild_id, index)
        if removed_song:
            await ctx.send(f"{ctx.author.mention} Removed a song from queue: {removed_song['title']}")
        else:
            await ctx.send("Failed to remove song from queue.")
        
    @commands.hybrid_command()
    async def pause(self, ctx : commands.Context):
        """Pause current song"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send('Paused')
        else:
            await ctx.send('Nothing is currently playing')
    
    @commands.hybrid_command()
    async def resume(self, ctx : commands.Context):
        """Resume current paused song"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send('Resumed')
        else:
            await ctx.send('Not Paused')
            
# Global optimized executor
executor = OptimizedExecutor(max_workers=2)

# Global instances
search_cache = OptimizedCache(max_size=20, ttl=300)  # Reduced from 50, shorter TTL
url_cache = OptimizedCache(max_size=20, ttl=600)     # URL cache lasts longer
performance_monitor = PerformanceMonitor()

# Global rate limiter
search_rate_limiter = RateLimiter(max_calls=10, time_window=60)  # 10 calls per minute
api_rate_limiter = RateLimiter(max_calls=5, time_window=60)      # 5 API calls per minute

# Global guild data manager
guild_data = GuildDataManager()

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
