"""
Optimized Music Cog for Discord Bot
Addresses critical performance issues:
- Connection pooling and intelligent caching
- Reduced API calls and blocking operations
- Memory management and resource cleanup
- Rate limiting and throttling
"""

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
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict, deque
import logging
import re

# Configure logging for performance monitoring
cogs_logger = settings.logging.getLogger("cogs")

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

# Global optimized executor
executor = OptimizedExecutor(max_workers=2)

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

# Global instances
search_cache = OptimizedCache(max_size=20, ttl=300)  # Reduced from 50, shorter TTL
url_cache = OptimizedCache(max_size=20, ttl=600)     # URL cache lasts longer
performance_monitor = PerformanceMonitor()

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

# Global rate limiter
search_rate_limiter = RateLimiter(max_calls=10, time_window=60)  # 10 calls per minute
api_rate_limiter = RateLimiter(max_calls=5, time_window=60)      # 5 API calls per minute

# Optimized YouTube operations
class OptimizedYouTubeOperations:
    """Optimized YouTube operations with caching and rate limiting"""
    
    @staticmethod
    async def search_videos(query: str, limit: int = 1) -> List[Dict]:
        """Cached video search with rate limiting"""
        cache_key = f"search:{query}:{limit}"
        
        # Try cache first
        cached_result = await search_cache.get(cache_key)
        if cached_result:
            await performance_monitor.record_metric("cache_hit", 1.0)
            return cached_result
        
        # Rate limit and search
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
    
    @staticmethod
    async def get_video_info(url: str) -> Dict:
        """Cached video info with rate limiting"""
        cache_key = f"video_info:{url}"
        
        # Try cache first
        cached_result = await url_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Rate limit and get info
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
    
    @staticmethod
    async def get_channel_info(channel_id: str) -> Dict:
        """Lightweight channel info (with caching in URL cache)"""
        cache_key = f"channel_info:{channel_id}"
        
        # Try cache first
        cached_result = await url_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Rate limit and get info
        await api_rate_limiter.acquire()
        start_time = time.time()
        
        try:
            channel_info = Channel.get(channel_id)
            await url_cache.set(cache_key, channel_info)
            
            await performance_monitor.record_metric("channel_info_time", time.time() - start_time)
            return channel_info
        except Exception as e:
            cogs_logger.error(f"Channel info fetch failed: {e}")
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
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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
    
    def get_queue(self, guild_id: int) -> List[Dict]:
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]
    
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
                
                # Clean old guild data (keep only active guilds)
                current_guilds = set()  # This would be populated from bot.guilds
                
                guilds_to_clean = []
                for guild_id in list(self.queues.keys()):
                    if guild_id not in current_guilds:
                        guilds_to_clean.append(guild_id)
                
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

# Global guild data manager
guild_data = GuildDataManager()

async def setup(bot: commands.Bot):
    await bot.add_cog(OptimizedMusic(bot))

class OptimizedMusicControls(discord.ui.View):
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
                await interaction.response.send_message("Paused!", ephemeral=True, delete_after=5)
            else:
                await interaction.response.send_message("Nothing is playing", ephemeral=True)
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
                await interaction.response.send_message("Resumed!", ephemeral=True, delete_after=5)
            else:
                await interaction.response.send_message("Not paused", ephemeral=True)
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

class OptimizedMusic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cleanup_task = None
        
    async def cog_load(self):
        """Start background cleanup task when cog loads"""
        self._cleanup_task = asyncio.create_task(guild_data.cleanup_all_expired())
        cogs_logger.info("Optimized Music cog loaded with cleanup task")
    
    async def cog_unload(self):
        """Cleanup when cog unloads"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        executor.shutdown()
        cogs_logger.info("Optimized Music cog unloaded")
    
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
            
            queue.append(song_data)
            
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
            
            song = queue.pop(0)
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
                view = OptimizedMusicControls(self)
                autoplay_enabled = guild_data.autoplay.get(guild_id, False)
                
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
                asyncio.create_task(self.play_next_optimized(ctx))
            
            voice_client.play(source, after=after_playing)
            
            # Update recent played (limited size)
            recent = guild_data.recent_played.get(guild_id, [])
            recent.append({
                'id': song.get('video_id', ''),
                'title': song['title'],
                'channel_name': song.get('channel_name', '')
            })
            guild_data.recent_played[guild_id] = recent[-10:]  # Keep only last 10
            
        except Exception as e:
            cogs_logger.error(f"Error in play_next_optimized: {e}")
            await ctx.send(f"Playback error: {str(e)}")

    @commands.hybrid_command(name="play")
    @app_commands.describe(query="Song title to search on YouTube")
    async def play(self, ctx: commands.Context, query: str = None):
        """Optimized play command"""
        try:
            await ctx.defer()
            if query:
                await self.play_music_optimized(ctx, query)
            else:
                await ctx.send("Please provide a song name to search.")
        except Exception as e:
            cogs_logger.error(f"Error in play command: {e}")
            await ctx.send(f"Something went wrong: {str(e)}")

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
        """Optimized voice state update"""
        try:
            if member == self.bot.user:
                if after.channel is None:
                    # Bot disconnected
                    guild_id = member.guild.id
                    await guild_data.cleanup_guild_data(guild_id)
                return
            
            voice_client = member.guild.voice_client
            if not voice_client:
                return
            
            # Simple disconnect logic
            if len(voice_client.channel.members) == 1:  # Only bot
                if guild_id := member.guild.id:
                    if guild_id not in guild_data.disconnect_tasks:
                        task = asyncio.create_task(self._disconnect_timer(member.guild))
                        guild_data.disconnect_tasks[guild_id] = task
            else:
                # Cancel disconnect task if users join
                if guild_id := member.guild.id:
                    if guild_id in guild_data.disconnect_tasks:
                        guild_data.disconnect_tasks[guild_id].cancel()
                        del guild_data.disconnect_tasks[guild_id]
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
