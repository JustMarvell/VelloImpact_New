import re
import yt_dlp
import asyncio
import discord
import settings
import traceback
import concurrent.futures
from discord.ext import commands

# logger
commands_logger = settings.logging.getLogger("commands")

# executor
executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)

# readonly
HEADERS = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}

YDL_OPTIONS_PLAYER = {
    'format' : 'bestaudio[acodec^=opus]/bestaudio/best',
    'noplaylist' : True,
    'quiet' : True,
    'no_warnings' : True,
    'extract_flat' : False,
    'source_address' : '0.0.0.0',
    'default_search' : 'auto',
    'skip_download' : True,
    'headers' : HEADERS
}

YDL_OPTIONS_RECOMENDATION = {
    'format' : 'bestaudio[acodec^=opus]/bestaudio/best',
    'quiet' : True,
    'no_warnings' : True,
    'extract_flat' : True,
    'source_address' : '0.0.0.0',
    'skip_download' : True,
    'playlistend' : 5,
}

FFMPEG_OPTIONS = {
    'before_options' : '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options' : '-vn -b:a 96k',
}

# =========================== NORMAL FUNCTION =========================
def get_video_id_from_url(url: str) -> str | None:
    """ Extract Youtube video ID from a URL """
    try:
        if not isinstance(url, str):
            return None
        patterns = [r"v=([A-Za-z0-9_-]{11})", r"youtu\.be/([A-Za-z0-9_-]{11})", r"/embed/([A-Za-z0-9_-]{11})", r"([A-Za-z0-9_-]{11})$"]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
    except Exception(BaseException) as e:
        raise e

def format_duration(seconds_or_str) -> str:
    """ Convert duration from seconds to MM:SS format 
    
    Args:
        seconds_or_str (int | str): Duration in seconds or already formatted string.
        
    Returns:
        Formatted duration string in MM:SS format.
    """
    try:
        # Handle if it's already in MM:SS format
        if isinstance(seconds_or_str, str):
            if ':' in seconds_or_str:
                return seconds_or_str
            seconds = int(seconds_or_str)
        else:
            seconds = int(seconds_or_str)

        return f"{seconds//60:02d}:{seconds%60:02d}"
    except (ValueError, TypeError):
        return str(seconds_or_str)
    
def format_view_count(count_or_str) -> str:
    """ convert view count to human-readable format
    
    Args:
         count_or_str: View count as an integer or string.
    Returns:
        Formatted view count string (e.g., '1.2M', '3.4K').
    """
    try:
        # Handle if it's already a formatted string
        if isinstance(count_or_str, str):
            if any(char in count_or_str for char in ['K', 'M', 'B']):
                return count_or_str
            count = int(count_or_str.replace(',', ''))
        else:
            count = int(count_or_str)
        
        # Determine scale
        if count >= 1_000_000_000:
            return f"{count / 1_000_000_000:.1f}B"
        elif count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            return f"{count / 1_000:.1f}K"
        else:
            return str(count)
    except (ValueError, TypeError):
        return str(count_or_str)
    
def get_queue(self, guild_id: int):
    """ Get or create queue for a guild 
    Args:
        self: self object
        guild_id: Current guild id
    """
    if guild_id not in self.queues:
        self.queues[guild_id] = []
    return self.queues[guild_id]
    
def log_error(msg: str) -> None:
    """ Send a log error message 
    Args:
        msg (str): Error message.
    """
    commands_logger.error(msg)
    
def log_info(msg: str) -> None:
    """ Send a log info message 
    Args:
        msg (str): Info message.
    """
    commands_logger.info(msg)
    
def show_queue(self, ctx: commands.Context) -> str | None:
    """ Returns current song queue 
    Args:
        self: self object
        ctx: commands.Context
    """
    guild_id = ctx.guild.id
    queue = get_queue(self=self, guild_id=guild_id)
    
    if not queue:
        return None
    else:
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue))
    
    return queue_list

# ================================= ASYNC FUNCTION ==================================
async def run_in_thread(_executor, func, *args):
    """ Run blocking function in a seperate thread """
    loop  = asyncio.get_event_loop()
    return await loop.run_in_executor(executor=_executor, func=func, *args)

async def disconnect_timer(self, guild: discord.Guild):
    """ Timer to disconnect after inactifity when alone 
    Args:
        self: self object
        guild: Current guild
    """
    await  asyncio.sleep(300) # 5 Minutes timer
    
    log_info(f"Disconnecting from {guild.name}. Reason : Idle for 5 minutes")
    voice_client = guild.voice_client
    
    try:
        if voice_client and len(voice_client.channel.members) == 1:
            await voice_client.disconnect(force=True)
            guild.voice_client = None
    except discord.Forbidden as e:
        log_error(f"Error during disconnect timer : {e}")
        pass
    
    try:
        if guild.id in self.queues:
            del self.queues[guild.id]
        if guild.id in self.current_songs:
            del self.current_songs[guild.id]
        if guild.id in self.autoplay:
            del self.autoplay[guild.id]
        if guild.id in self.recent_played:
            del self.recent_played[guild.id]
    except Exception(BaseException) as e:
        log_error(f"Error during cleaning up in disconnect timer : {e}")
        pass
    
    try:
        if guild.id in self.disconnect_task:
            del self.disconnect_task[guild.id]
        log_info(f"Disconnected from voice channel in guild {guild.name} ({guild.id}) due to inactivity.")
    except Exception(BaseException) as e:
        log_error(f"Error removing disconnect task for guild {guild.name} : {e}")
        pass
    
async def get_audio_source(song_url: str) -> str:
    """ Extract direct audio url using yt_dlp in a thread to avoid blocing the async loop
     Args:
         song_url: url of the song
     """
    def extract():
        with yt_dlp.YoutubeDL(YDL_OPTIONS_PLAYER) as ydl:
            info = ydl.extract_info(song_url, download=False)
            return info['url']
        
    max_retries = 2
    for attempt in range(max_retries):
        try:
            audio_url = await run_in_thread(_executor=executor, func=extract)
            return audio_url
        except asyncio.exceptions.TimeoutError or Exception(BaseException) as e:
            if attempt < max_retries - 1:
                log_info(f"Falied to extract audio url in get_audio_source. Retrying...")
                continue
            else:
                log_error(f"Failed to extract audio url in get_audio_source. Abort! : {e}")
                raise e

    raise Exception("Failed to get audio url")

async def play_next(self, ctx: commands.Context):
    """ Play a song and send discord embed
     Args:
         self: self object
         ctx: commands.Context
     """
    if not ctx.voice_client:
        return
    
    voice_client = ctx.voice_client
    guild_id = ctx.guild.id
    queue = get_queue(self=self, guild_id=guild_id)
    
    if not queue:
        await ctx.send("Queue is empty! add more song's or use autoplay", delete_after=5)
        
        # TODO : Change bot's status
        return
    
    song = queue.pop(0)    
    self.current_songs[guild_id] = song
    url = song['url']
    
    try:
        audio_url = await run_in_thread(get_audio_source, url)
    except Exception(BaseException) as e:
        await ctx.send(f"Failed to get audio stream {e}. | Current song will be cleaned and skipped!", ephemeral=True, delete_after=5)
        log_error(f"Failed to get audio stream in play_next : {e} | Cleaning up current song!. Next song(if available) will be played instead")
        
        # clean up current song if extraction failed
        if guild_id in self.current_songs:
            del self.current_songs[guild_id]
        # Try to play next if queue has more
        if queue:
            log_info(f"Next song detected!. Playing...")
            await play_next(self, ctx)
        return
            
    def custom_probe():
        codec = 'opus'
        bitrate = '96k'
        return codec, bitrate
    
    source = await discord.FFmpegOpusAudio.from_probe(audio_url, method=custom_probe, executable='ffmpeg', **FFMPEG_OPTIONS)
    
    def after_playing():
        coro = play_next(self, ctx)
        fut = asyncio.run_coroutine_threadsafe(coro, loop=self.bot.loop)
        try:
            fut.result()
        except asyncio.CancelledError or Exception(BaseException) as err:
            log_error(f"Failed to play next song in after_playing() : {err}")
    
    try:
        voice_client.play(source, after=after_playing)
    except Exception(BaseException) as er:
        await ctx.send(f"Failed to play using voice client: {er}")
        log_error(f"Failed to play using voice client: {er} | {traceback.format_exc()}")