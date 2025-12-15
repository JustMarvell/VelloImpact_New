import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from youtubesearchpython import *
from controllers.channel_genre import infer_channel_genre
from controllers.lyrics_fetcher import fetch_song_lyrics, is_genius_available
import yt_dlp
import settings
import time
import concurrent.futures

# Add this at the top with other imports
executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)

cogs_logger = settings.logging.getLogger("cogs")

search_cache = {}
url_cache = {}

#region : defs

async def run_in_thread(fn, *args, **kwargs):
    """Helper to safely run blocking functions in a thread"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, fn, *args, **kwargs)

def get_video_id_from_url(url: str) -> str:
    """Extract YouTube video ID from a URL or return original if not found."""
    try:
        import re
        if not isinstance(url, str):
            return ''
        patterns = [r"v=([A-Za-z0-9_-]{11})", r"youtu\.be/([A-Za-z0-9_-]{11})", r"/embed/([A-Za-z0-9_-]{11})", r"([A-Za-z0-9_-]{11})$"]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
    except Exception:
        return ''
    return ''

def normalize_youtube_link(link: str) -> str:
    """Normalize various YouTube URL formats to the canonical full URL.

    Supported inputs:
    - https://www.youtube.com/watch?v=VIDEOID
    - https://youtu.be/VIDEOID
    - https://www.youtube.com/embed/VIDEOID
    - raw VIDEOID

    If no 11-character video id is found, returns the original link unchanged.
    """
    try:
        import re
        if not isinstance(link, str):
            return link

        # Look for the 11-character YouTube video id in several common patterns
        patterns = [
            r"v=([A-Za-z0-9_-]{11})",
            r"youtu\.be/([A-Za-z0-9_-]{11})",
            r"/embed/([A-Za-z0-9_-]{11})",
            r"([A-Za-z0-9_-]{11})$",
        ]
        for p in patterns:
            m = re.search(p, link)
            if m:
                return f"https://www.youtube.com/watch?v={m.group(1)}"
    except Exception:
        # If normalization fails for any reason, return original link
        return link

    return link

def format_duration(seconds_or_str) -> str:
    """Convert duration from seconds (int/str) to MM:SS format.
    
    Args:
        seconds_or_str: Duration as seconds (int, str, or already formatted string)
        
    Returns:
        Formatted duration string as MM:SS
    """
    try:
        # Handle if it's already in MM:SS format or other string format
        if isinstance(seconds_or_str, str):
            # If it already contains ':', assume it's already formatted
            if ':' in seconds_or_str:
                return seconds_or_str
            seconds = int(seconds_or_str)
        else:
            seconds = int(seconds_or_str)
        
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        # If conversion fails, return the original value
        return str(seconds_or_str)

def format_view_count(count_or_str) -> str:
    """Convert view count to human-readable format (K/M/B).
    
    Args:
        count_or_str: View count as int, str, or already formatted string
        
    Returns:
        Formatted view count string (e.g., "1.2K", "1.5M", "2.3B")
    """
    try:
        # Handle if it's already formatted (contains K, M, B)
        if isinstance(count_or_str, str):
            if any(c in count_or_str for c in ['K', 'M', 'B']):
                return count_or_str
            # Remove any commas and try to convert to int
            count = int(count_or_str.replace(',', ''))
        else:
            count = int(count_or_str)
        
        # Determine the appropriate scale
        if count >= 1_000_000_000:
            # Billions
            return f"{count / 1_000_000_000:.1f}B"
        elif count >= 1_000_000:
            # Millions
            return f"{count / 1_000_000:.1f}M"
        elif count >= 1_000:
            # Thousands
            return f"{count / 1_000:.1f}K"
        else:
            return str(count)
    except (ValueError, TypeError):
        # If conversion fails, return the original value
        return str(count_or_str)

async def setup(bot : commands.Bot):
    await bot.add_cog(Music(bot))
    
#endregion
    
class MusicControls(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None) # Persisent view
        # Keep a reference to the Music cog so the button can toggle autoplay
        self.cog = cog
        
    @discord.ui.button(label="⏸", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.pause()
            self.pause_button.disabled = True
            self.resume_button.disabled = False
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("Nothing is playing", ephemeral=True)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, disabled=True)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_paused():
            voice_client.resume()
            self.pause_button.disabled = False
            self.resume_button.disabled = True
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("Not paused", ephemeral=True)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        else:
            await interaction.response.send_message("Nothing is playing to skip!", ephemeral=True)

    @discord.ui.button(label="⏹", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        
        guild_id = interaction.guild.id
        self.cog.get_queue(guild_id).clear()
        if guild_id in self.cog.current_songs:
            del self.cog.current_songs[guild_id]
            
        voice_client.stop()
        self.pause_button.disabled = True
        self.resume_button.disabled = True
        self.skip_button.disabled = True
        
        # remove current activity
        try:
            await self.cog.bot.change_presence(activity=discord.Game(name="Hide and Seek", platform="Closet"))
        except Exception as e:
            print(f"Error removing bot status: {e}")
            pass
        
        await interaction.response.edit_message(view=self)

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
        was_enabled = self.cog.autoplay.get(gid, False)
        now_enabled = not was_enabled
        self.cog.autoplay[gid] = now_enabled

        # Update button appearance
        button.label = f"Autoplay: {'🟢' if now_enabled else '🔴'}"
        button.style = discord.ButtonStyle.success if now_enabled else discord.ButtonStyle.secondary

        await interaction.response.edit_message(view=self)
        
        # ———————— NEW: AUTO-START MUSIC WHEN TURNING ON ————————
        if now_enabled and not was_enabled:  # Was off → now on
            if len(self.cog.get_queue(gid)) == 0:  # Queue is empty → let's fill it!
                ctx = await self.cog.bot.get_context(interaction.message)

                # Try to base it on the last played song
                recent = self.cog.recent_played.get(gid, [])
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
                        await self.cog.play_next(ctx)
                    except:
                        pass  # play_next will handle errors

    @discord.ui.button(label="☰", style=discord.ButtonStyle.secondary)
    async def show_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show the current music queue."""
        queue = self.cog.get_queue(interaction.guild.id)
        
        if not queue:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return
        
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue[:10]))
        
        if len(queue) > 10:
            queue_list += f"\n... and {len(queue) - 10} more song(s)"
        
        await interaction.response.send_message(f"**Current Queue:**\n{queue_list}")
        
    # clear queue button
    @discord.ui.button(label="🗑️ Clear Queue", style=discord.ButtonStyle.danger)
    async def clear_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear the current music queue."""
        guild_id = interaction.guild.id
        self.cog.get_queue(guild_id).clear()
        await interaction.response.send_message("Cleared the music queue.", ephemeral=True, delete_after=4)

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
        if guild_id not in self.cog.current_songs:
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
            song = self.cog.current_songs[guild_id]

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
            max_field_length = 1024
            if len(lyrics_text) <= max_field_length:
                embed.add_field(name="Lyrics", value=lyrics_text, inline=False)
            else:
                chunks = []
                current_chunk = ""
                
                lines = lyrics_text.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= max_field_length:
                        current_chunk += line + '\n'
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line + '\n'
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
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
    channel = None
    
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self.autoplay = {}
        self.recent_played = {}
        self.queues = {}
        self.current_songs = {}
        self.disconnect_tasks = {}
        
    def get_queue(self, guild_id: int):
        """Get or create queue for a guild"""
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        return self.queues[guild_id]
    
    async def get_audio_source(self, song_url: str):
        """ Extract direct audio URL using yt_dlp in a thread to avoid blocking the async loop """
        
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        }
        
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'quiet': True,
            'no_warnings': True,
            'headers': headers,
        }
        
        def extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(song_url, download=False)
                return info['url']
            
        max_retries = 3
        for attempt in range(max_retries):
            try:
                audio_url = await run_in_thread(extract)
                return audio_url
            except Exception as e:
                if attempt < max_retries - 1:
                    # Could log or send temporary message here if desired
                    continue
                else:
                    raise Exception(f"Failed to extract audio URL after {max_retries} attempts: {str(e)}")
        
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild = member.guild
        voice_client = guild.voice_client

        if member == self.bot.user:
            # Bot was disconnected (e.g., by Discord idle timeout)
            if after.channel is None:
                try:
                    guild_id = guild.id
                    self.get_queue(guild_id).clear() 
                    if guild_id in self.current_songs:
                        del self.current_songs[guild_id]
                    voice_client.stop()
                    
                    if guild.id in self.disconnect_tasks:
                        del self.disconnect_tasks[guild.id]
                        
                    cogs_logger.info(f"Bot disconnected from voice channel in guild {guild.name} ({guild.id})")
                except Exception as e:
                    cogs_logger.error(f"Error handling bot disconnection: {e}")
                    pass
            return

        if voice_client is None:
            return

        channel = voice_client.channel
        if len(channel.members) == 1:  # Only bot left
            if guild.id in self.disconnect_tasks:
                return  # Timer already running
            task = self.bot.loop.create_task(self.disconnect_timer(guild))
            self.disconnect_tasks[guild.id] = task
        else:
            # Users present: cancel any timer
            if guild.id in self.disconnect_tasks:
                self.disconnect_tasks[guild.id].cancel()
                del self.disconnect_tasks[guild.id]
                
    async def disconnect_timer(self, guild: discord.Guild):
        """Timer to disconnect after inactivity when alone"""
        await asyncio.sleep(300)  # 5 minutes
        voice_client = guild.voice_client
        try:
            if voice_client and len(voice_client.channel.members) == 1:
                await voice_client.disconnect(force=True)
                guild.voice_client = None 
        except Exception as e:
            cogs_logger.error(f"Error during disconnect timer for guild {guild.name}: {e}")
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
            except Exception as e:
                cogs_logger.error(f"Error cleaning up after disconnect in {guild.name}: {e}")
                pass

        try:
            if guild.id in self.disconnect_tasks:
                del self.disconnect_tasks[guild.id]
            cogs_logger.info(f"Disconnected from voice channel in guild {guild.name} ({guild.id}) due to inactivity.")
        except Exception as e:
            cogs_logger.error(f"Error removing disconnect task for {guild.name}: {e}")
            pass
    
    @commands.hybrid_command()
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
            
    @commands.hybrid_command()
    async def release(self, ctx : commands.Context):
        """ Leave a voice Channel """
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        if ctx.voice_client:
            queue.clear()
            self.channel = None
            
            try:
                await self.bot.change_presence(activity=discord.Game(name="Hide and seek", platform="Closet"))
                # await self.bot.change_presence(activity=discord.Activity(state=discord.ActivityType.playing, name="Your Mom"))
            except Exception as e:
                print(f"Error removing bot status: {e}")
                pass
            
            try:
                if guild_id in self.current_songs:
                    del self.current_songs[guild_id]

                await ctx.voice_client.disconnect(force=True)
                try:
                    ctx.guild.voice_client = None
                except Exception:
                    pass
                
                if ctx.guild.id in self.disconnect_tasks:
                    del self.disconnect_tasks[ctx.guild.id]
            except Exception as e:
                await ctx.send(f"Error disconnecting: {e}", ephemeral=True)
                pass
                
            await ctx.send('kbay')
        else:
            await ctx.send("I'm not in a voice channel")
    
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
                    await self.play_music(ctx, query)
                except Exception as e:
                    await ctx.send(f"Something went wrong : {e}")
            elif link:
                try :
                    await self.play_music_by_url(ctx, link)
                except Exception as e:
                    await ctx.send(f"Something went wrong : {e}")
            else:
                await ctx.send("Please provide either a song name (query) or a YouTube link.")
        except Exception as e:
            await ctx.send(f"Something went wrong : {e}")
    
    async def play_music(self, ctx : commands.Context, querry : str):
        try : 
            guild_id = ctx.guild.id
            q = self.get_queue(guild_id)
            
            if len(q) >= 20: 
                await ctx.send("Queue is full! Max 20 songs.")
                return
            
            if not ctx.author.voice:
                await ctx.send('You need to join a voice channel first to use me!')
                return

            if not ctx.voice_client:
                self.channel = ctx.author.voice.channel
                await self.channel.connect()
                await ctx.send(f'I have been summoned to join {self.channel.name}')
                voice_client = ctx.voice_client
            else:
                voice_client = ctx.voice_client
            
            if querry in search_cache:
                results = search_cache[querry]
            else:
                try:
                    search = VideosSearch(query=querry, limit=1)
                    results = search.result()['result']
                    if len(search_cache) >= 50:
                        search_cache.pop(next(iter(search_cache)))
                    search_cache[querry] = results
                except Exception as e:
                    await ctx.send(f"Error searching YouTube: {str(e)}")
                    return
            
            if not results:
                await ctx.send(f'No music found for {querry}')
                return
                
            video = results[0]
            url = video['link']
            title = video['title']
            thumbnail = video['thumbnails'][0]['url']
            channel_id = video['channel']['id']
            channel_thumbnails = Channel.get(channel_id)['thumbnails'][0]['url']
            channel_url = Channel.get(channel_id)['url']
            channel_name = Channel.get(channel_id)['title']
            duration = format_duration(video['duration'])
            view_count = format_view_count(video['viewCount']['short'])

            video_id = get_video_id_from_url(url) or ''
            q.append({'url': url, 'video_id': video_id, 'title': title, 'thumbnail': thumbnail, 'channel_thumbnails': channel_thumbnails, 'channel_name': channel_name, 'channel_id': channel_id, 'duration': duration, 'view_count': view_count, 'channel_url': channel_url})

            if not voice_client.is_playing():
                await self.play_next(ctx)
            else:
                await ctx.send(f"Added to queue: {title}")
        except Exception as e:
            await ctx.send(f"Something went wrong on internal play_music : {e}")
            
    async def play_music_by_url(self, ctx : commands.Context, link : str):
        try : 
            guild_id = ctx.guild.id
            q = self.get_queue(guild_id)
            
            if len(q) >= 20:
                await ctx.send("Queue is full! Max 20 songs.")
                return
            
            if not ctx.author.voice:
                await ctx.send('You need to join a voice channel first to use me!')
                return

            if not ctx.voice_client:
                self.channel = ctx.author.voice.channel
                await self.channel.connect()
                await ctx.send(f'I have been summoned to join {self.channel.name}')
                voice_client = ctx.voice_client
            else:
                voice_client = ctx.voice_client
                
            normalized_link = normalize_youtube_link(link)

            if normalized_link in url_cache:
                result = url_cache[normalized_link]
            else:
                try:
                    video_info = Video.getInfo(normalized_link, mode = ResultMode.json)

                    result = video_info

                    if len(url_cache) >= 50:
                        url_cache.pop(next(iter(url_cache)))
                    url_cache[normalized_link] = result
                except Exception as e:
                    await ctx.send(f"Error searching YouTube: {str(e)}")
                    return
            
            if not result:
                await ctx.send(f'No music found for {link}')
                return
                
            video = result
            url = video['link']
            title = video['title']
            thumbnail = video['thumbnails'][0]['url']
            channel_id = video['channel']['id']
            channel_thumbnails = Channel.get(channel_id)['thumbnails'][0]['url']
            channel_url = Channel.get(channel_id)['url']
            channel_name = Channel.get(channel_id)['title']
            duration_raw = video['duration']['secondsText'] if isinstance(video.get('duration'), dict) else video.get('duration')
            duration = format_duration(duration_raw)
            view_count = format_view_count(video['viewCount']['text'])

            video_id = get_video_id_from_url(url) or ''
            q.append({'url': url, 'video_id': video_id, 'title': title, 'thumbnail': thumbnail, 'channel_thumbnails': channel_thumbnails, 'channel_name': channel_name, 'channel_id': channel_id, 'duration': duration, 'view_count': view_count, 'channel_url': channel_url})

            if not voice_client.is_playing():
                await self.play_next(ctx)
            else:
                await ctx.send(f"Added to queue: {title}")
        except Exception as e:
            await ctx.send(f"Something went wrong on internal play_music_by_url : {e}")
    
    async def add_autoplay_suggestions(self, ctx: commands.Context, guild_id: int, count: int = 1):
        """Use yt_dlp to get REAL YouTube 'Up Next' / related videos for true autoplay"""
        try:
            """Fetch REAL YouTube autoplay recommendations safely in a thread"""
            if not ctx.guild or not ctx.voice_client:
                return 0

            recent = self.recent_played.get(guild_id, [])
            if not recent:
                return 0

            last_song = recent[-1]
            video_id = last_song.get('id') or get_video_id_from_url(last_song.get('url', ''))
            if not video_id:
                return 0

            # Collect IDs to avoid duplicates
            played_ids = {item.get('id') for item in recent if item.get('id')}
            queued_ids = {song.get('video_id') for song in self.get_queue(guild_id) if song.get('video_id')}
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
                    print(f"[Autoplay] yt_dlp failed: {e}")
                    return []

            try:
                entries = await run_in_thread(fetch_related)
            except Exception as e:
                print(f"[Autoplay] Thread execution failed: {e}")
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
                        ch_info = await run_in_thread(Channel.get, channel_id)
                        channel_name = ch_info.get('title', channel_name)
                        if ch_info.get('thumbnails'):
                            channel_thumbnails = ch_info['thumbnails'][0]['url']
                        channel_url = ch_info.get('url', channel_url)
                    except:
                        pass

                self.get_queue(guild_id).append({'url': url, 'video_id': vid_id, 'title': title, 'thumbnail': thumbnail, 'channel_name': channel_name, 'channel_id': channel_id or '', 'duration': duration, 'view_count': '', 'channel_thumbnails': channel_thumbnails, 'channel_url': channel_url})

                seen.add(vid_id)
                added += 1

            if added > 0:
                try:
                    await ctx.send(f"Autoplay added {added} new song(s)", delete_after=5)
                except:
                    pass

            return added

        except Exception as e:
            print(f"Autoplay error: {e}")
            return 0
    
    async def play_next(self, ctx: commands.Context):
        try :
            if not ctx.voice_client:
                return
            
            voice_client = ctx.voice_client
            guild_id = ctx.guild.id
            q = self.get_queue(guild_id)
            
            if not q:
                await ctx.send("Queue is empty!", ephemeral=True, delete_after=5)
                
                # remove current bot status
                try:
                    await self.bot.change_presence(activity=discord.Game(name="Hide and seek", platform="Closet"))
                    try:
                        if guild_id in self.current_songs:
                            del self.current_songs[guild_id]
                    except Exception:
                        pass
                except Exception as e:
                    print(f"Error removing bot status: {e}")
                    pass
                return
            
            song = q.pop(0)
            
            self.current_songs[guild_id] = song
            
            url = song['url']
            title = song['title']
            thumbnail = song['thumbnail']
            channel_thumbnails = song['channel_thumbnails']
            channel_name = song['channel_name']
            channel_url = song['channel_url']
            duration = song['duration']
            view_count = song['view_count']
            
            print(url)
            
            view = MusicControls(self)
            view.pause_button.disabled = False
            view.resume_button.disabled = True
            try:
                if ctx.guild:
                    enabled = self.autoplay.get(ctx.guild.id, False)
                    view.autoplay_button.label = f"Autoplay: {'🟢' if enabled else '🔴'}"
                    view.autoplay_button.style = discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary
            except Exception:
                pass

            embed = discord.Embed(title=f'Now Playing : ')
            embed.set_author(name=channel_name, url=channel_url)
            embed.set_thumbnail(url='https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png')
            embed.set_footer(text=channel_name, icon_url=channel_thumbnails)
            embed.add_field(name=title, value=f'Duration : {duration}\nView Count : {view_count}')
            embed.set_image(url = thumbnail)
            
            try:
                # send discord embed
                await ctx.send(embed=embed, view=view)
                
                activity = discord.Activity(type=discord.ActivityType.listening, 
                                            name=f"🎵 {title}", 
                                            url=url,
                                            details=f"Uploaded to Youtube By: {channel_name}", 
                                            platform='YouTube', 
                                            details_url=channel_url)
                
                await self.bot.change_presence(activity=activity)
                
            except Exception as e:
                print(f"error : {e}")
                pass
        except Exception as e:
            await ctx.send(f"Failed to send Embed : {e}")
            
        # (old headers)
        # headers = {
        #     "authority": "www.google.com",
        #     "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        #     "accept-language": "en-US,en;q=0.9",
        #     "cache-control": "max-age=0",
        #     "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        #     'sec-ch-ua': '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
        #     'sec-ch-ua-platform': 'Windows',
        #     'sec-ch-ua-platform-version': '15.0.0',
        # }

        # ydl_opts = {
        #     'format': 'bestaudio[ext=m4a]',
        #     'quiet': True,
        #     'no_warnings': True,
        #     'headers' : headers
        # }
        
        # max_retries = 3
        # for attempt in range(max_retries):
        #     try:
        #         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        #             info = ydl.extract_info(url, download=False)
        #             audio_url = info['url']  # Direct stream URL
        #             print(audio_url)
        #         break
        #     except Exception as e:
        #         if attempt < max_retries - 1:
        #             await ctx.send(f"Error fetching audio, retrying... ({attempt+1}/{max_retries})")
        #             continue
        #         else:
        #             await ctx.send(f"Failed to fetch audio after {max_retries} attempts: {str(e)}")
        #             return
                
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -b:a 96k'
        }
        
        # try:
        #     source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
        # except Exception as e:
        #     await ctx.send(f"Failed to play : {e}")
        
        # New: Offload yt_dlp extraction to thread for better responsiveness
        try:
            audio_url = await self.get_audio_source(url)
        except Exception as e:
            await ctx.send(f"Failed to fetch audio stream: {str(e)}")
            # Clean up current song if extraction failed
            if guild_id in self.current_songs:
                del self.current_songs[guild_id]
            # Try to play next if queue has more
            if q:
                await self.play_next(ctx)
            return
        
        source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
        
        def after_playing(error):
            import asyncio
            coro = self.play_next(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, loop=self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"Error in play_next: {e}")
                
        try :
            voice_client.play(source, after=after_playing)
        except Exception as e:
            await ctx.send(f"Failed to play using voice client : {e}", ephemeral=True, delete_after=5)
            
        try:
            if guild_id:
                vid = song.get('video_id', '')
                if vid:
                    lst = self.recent_played.get(guild_id, [])
                    lst.append({'id': vid, 'title': title, 'channel_id': song.get('channel_id'), 'channel_name': channel_name})
                    self.recent_played[guild_id] = lst[-20:]

                if self.autoplay.get(guild_id, False) and len(q) < 3:
                    await self.add_autoplay_suggestions(ctx, guild_id, count=3)
        except Exception as e:
            print(f"Error handling autoplay post-play: {e}")
        
    @commands.hybrid_command()
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
            q = self.get_queue(guild_id)
            if not q and guild_id not in self.current_songs:
                await ctx.send("Please provide a song name, or play a song first.")
                return
            if guild_id in self.current_songs:
                song_query = self.current_songs[guild_id].get('title', '')
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
            
            max_field_length = 1024
            if len(lyrics_text) <= max_field_length:
                embed.add_field(name="Lyrics", value=lyrics_text, inline=False)
            else:
                chunks = []
                current_chunk = ""
                
                lines = lyrics_text.split('\n')
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= max_field_length:
                        current_chunk += line + '\n'
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line + '\n'
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
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
    async def show_queue(self, ctx: commands.Context):
        """Show current song queue"""
        guild_id = ctx.guild.id
        queue = self.get_queue(guild_id)
        
        if not queue:
            await ctx.send("The queue is empty.")
            return
        
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue))
        await ctx.send(f"Current queue:\n{queue_list}")
        
    @commands.hybrid_command()
    async def clear_queue(self, ctx: commands.Context):
        """Clear current queue"""
        guild_id = ctx.guild.id
        self.get_queue(guild_id).clear()
        await ctx.send("Queue cleared.")
        
    @commands.hybrid_command()
    async def skip(self, ctx: commands.Context):
        """Skip current song"""
        if not ctx.voice_client:
            await ctx.send("Not in a voice channel!")
            return
        
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await ctx.send("Nothing is playing to skip!")
            return
        
        ctx.voice_client.stop()
        await ctx.send("Skipped current song")
        
    @commands.hybrid_command()
    async def remove(self, ctx: commands.Context, index: int):
        """Remove song at specified index"""
        guild_id = ctx.guild.id
        q = self.get_queue(guild_id)
        if not q:
            await ctx.send("The queue is empty.")
            return
        
        index = index - 1
        if index < 0 or index >= len(q):
            await ctx.send(f"Invalid index. Use a number between 1 and {len(q)}.")
            return
        
        removed_song = q.pop(index)
        await ctx.send(f"Removed from queue: {removed_song['title']}")
        
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
            
    @commands.hybrid_command()
    async def stop(self, ctx : commands.Context):
        """Stop playing song"""
        if ctx.voice_client:
            guild_id = ctx.guild.id
            self.get_queue(guild_id).clear() 
            if guild_id in self.current_songs:
                del self.current_songs[guild_id]
            ctx.voice_client.stop()
            
            # remove current activity
            try:
                await self.bot.change_presence(activity=discord.Game(name="Hide and seek", platform="Closet"))
            except Exception as e:
                print(f"Error removing bot status: {e}")
                pass
            
            await ctx.send("Stopped")
        else:
            await ctx.send("Nothing to stop")