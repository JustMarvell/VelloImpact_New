import discord
from discord.ext import commands
from discord import app_commands
from youtubesearchpython import *
from controllers.channel_genre import infer_channel_genre
from controllers.lyrics_fetcher import fetch_song_lyrics, is_genius_available
import yt_dlp
import settings
import time

queue = []
search_cache = {}
url_cache = {}


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
        global queue
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        queue.clear()
        voice_client.stop()
        self.pause_button.disabled = True
        self.resume_button.disabled = True
        self.skip_button.disabled = True
        
        # remove current activity
        try:
            await self.bot.change_presence(activity=discord.Activity(state=discord.ActivityType.playing, name="Your Mom"))
        except Exception as e:
            print(f"Error removing bot status: {e}")
            pass
        
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Autoplay: 🔴", style=discord.ButtonStyle.secondary)
    async def autoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle autoplay for the guild. When enabled, the bot will auto-add suggestions."""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Autoplay only available in guilds.", ephemeral=True)
            return

        gid = guild.id
        enabled = not self.cog.autoplay.get(gid, False)
        self.cog.autoplay[gid] = enabled

        # Update button presentation
        button.label = f"Autoplay: {'🟢' if enabled else '🔴'}"
        button.style = discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="☰", style=discord.ButtonStyle.secondary)
    async def show_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show the current music queue."""
        global queue
        if not queue:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return
        
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue[:10]))
        
        if len(queue) > 10:
            queue_list += f"\n... and {len(queue) - 10} more song(s)"
        
        await interaction.response.send_message(f"**Current Queue:**\n{queue_list}")

    @discord.ui.button(label="📝 Lyrics", style=discord.ButtonStyle.secondary)
    async def lyrics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Fetch and display lyrics for the currently playing song."""
        from controllers.lyrics_fetcher import fetch_song_lyrics, is_genius_available
        
        if not is_genius_available():
            await interaction.response.send_message(
                "❌ Lyrics feature is not available. The bot owner needs to configure the Genius API token.",
                ephemeral=True
            )
            return
        
        current_song = self.cog.current_song
        if not current_song or not current_song.get('title'):
            await interaction.response.send_message("No song is currently playing.", ephemeral=True)
            return
        
        try : 
            tempmsg = await interaction.response.send_message(
                "🎵 Searching for lyrics...",
                ephemeral=True
            )
            await interaction.response.defer(ephemeral=True)
        except Exception:
            pass
            
        try:
            song_title = current_song.get('title', '')
            artist_name = current_song.get('channel_name', '')
            
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
        self.current_song = {}
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not member.bot or member != self.bot.user:
            return
        voice_client = member.guild.voice_client
        if voice_client and len(voice_client.channel.members) == 1:  # Bot is alone
            global queue
            queue.clear()
            await voice_client.disconnect()
            channel = self.bot.get_channel(voice_client.channel.id)
            if channel:
                await channel.send("Disconnected due to empty voice channel.")
    
    @commands.hybrid_command()
    async def arise(self, ctx : commands.Context):
        """ Join a Voice Channel """
        if ctx.author.voice:
            if self.channel == None:
                self.channel = ctx.author.voice.channel
                await self.channel.connect()
                await ctx.send(f'I have been summoned to join {self.channel.name}')
            else:
                await ctx.send("I'm already in a channel :v")
                return
        else:
            await ctx.send('Please join a voice channel first!')
            
    @commands.hybrid_command()
    async def release(self, ctx : commands.Context):
        """ Leave a voice Channel """
        global queue
        if ctx.voice_client:
            queue.clear()
            self.channel = None
            
            try:
                await self.bot.change_presence(activity=discord.Activity(state=discord.ActivityType.playing, name="Your Mom"))
            except Exception as e:
                print(f"Error removing bot status: {e}")
                pass
            
            await ctx.voice_client.disconnect()
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
            if len(queue) >= 20: 
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
            queue.append({'url': url, 'video_id': video_id, 'title': title, 'thumbnail': thumbnail, 'channel_thumbnails': channel_thumbnails, 'channel_name': channel_name, 'channel_id': channel_id, 'duration': duration, 'view_count': view_count, 'channel_url': channel_url})

            if not voice_client.is_playing():
                await self.play_next(ctx)
            else:
                await ctx.send(f"Added to queue: {title}")
        except Exception as e:
            await ctx.send(f"Something went wrong on internal play_music : {e}")
            
    async def play_music_by_url(self, ctx : commands.Context, link : str):
        try : 
            if len(queue) >= 20:
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
            queue.append({'url': url, 'video_id': video_id, 'title': title, 'thumbnail': thumbnail, 'channel_thumbnails': channel_thumbnails, 'channel_name': channel_name, 'channel_id': channel_id, 'duration': duration, 'view_count': view_count, 'channel_url': channel_url})

            if not voice_client.is_playing():
                await self.play_next(ctx)
            else:
                await ctx.send(f"Added to queue: {title}")
        except Exception as e:
            await ctx.send(f"Something went wrong on internal play_music_by_url : {e}")
    
    async def add_autoplay_suggestions(self, ctx: commands.Context, guild_id: int, count: int = 5):
        """Fetch related videos based on recent played and append up to `count` new songs to the queue."""
        try:
            recent = self.recent_played.get(guild_id, [])
            if not recent:
                return 0
            last_item = recent[-1]
            last_title = last_item.get('title') if isinstance(last_item, dict) else None
            last_channel_id = last_item.get('channel_id') if isinstance(last_item, dict) else None
            last_channel_name = last_item.get('channel_name') if isinstance(last_item, dict) else None
            suggestions = []
            try:
                genre_label = None
                if last_channel_id:
                    try:
                        ginfo = infer_channel_genre(last_channel_id)
                        if ginfo and ginfo.get('genre'):
                            genre_label = ginfo.get('genre')
                    except Exception:
                        genre_label = None

                if last_title:
                    search_query = f"{last_title} {genre_label}" if genre_label else last_title
                    search = VideosSearch(query=search_query, limit=25)
                    res = search.result()
                    raw_suggestions = res.get('result', []) if isinstance(res, dict) else res

                    suggestions = []
                    for r in raw_suggestions:
                        if r.get('title') == last_title:
                            continue
                        channel_id = (r.get('channel') or {}).get('id', '')
                        if last_channel_id and channel_id == last_channel_id:
                            suggestions.append(r)

                    if len(suggestions) < count:
                        for r in raw_suggestions:
                            if r.get('title') == last_title:
                                continue
                            channel_id = (r.get('channel') or {}).get('id', '')
                            if last_channel_id and channel_id == last_channel_id:
                                continue
                            suggestions.append(r)
                            if len(suggestions) >= count:
                                break
                else:
                    suggestions = []
            except Exception:
                suggestions = []

            added = 0
            for r in suggestions:
                if added >= count:
                    break
                link = r.get('link') or ''
                vid_id = get_video_id_from_url(link)
                if not vid_id:
                    continue
                recent_ids = [r.get('id') if isinstance(r, dict) else r for r in recent]
                if vid_id in recent_ids or any(s.get('video_id') == vid_id for s in queue):
                    continue

                title = r.get('title')
                thumbnail = ''
                try:
                    thumbnail = r.get('thumbnails', [])[0].get('url', '')
                except Exception:
                    thumbnail = ''
                channel_id = (r.get('channel') or {}).get('id', '')
                channel_name = (r.get('channel') or {}).get('name', '')
                try:
                    channel_thumbnails = Channel.get(channel_id)['thumbnails'][0]['url'] if channel_id else ''
                    channel_url = Channel.get(channel_id)['url'] if channel_id else ''
                    channel_name = Channel.get(channel_id)['title'] if channel_id else channel_name
                except Exception:
                    channel_thumbnails = ''
                    channel_url = ''
                    channel_name = channel_name

                duration_raw = r.get('duration')
                duration = format_duration(duration_raw)
                view_count = format_view_count((r.get('viewCount') or {}).get('text') or r.get('viewCount') or 0)

                queue.append({'url': link, 'video_id': vid_id, 'title': title, 'thumbnail': thumbnail, 'channel_thumbnails': channel_thumbnails, 'channel_name': channel_name, 'channel_id': channel_id, 'duration': duration, 'view_count': view_count, 'channel_url': channel_url})
                added += 1

            if added > 0:
                try:
                    await ctx.send(f"Autoplay added {added} suggested song(s) to the queue.")
                except Exception:
                    if ctx.channel:
                        await ctx.channel.send(f"Autoplay added {added} suggested song(s) to the queue.")
            return added
        except Exception as e:
            print(f"Autoplay suggestion error: {e}")
            return 0
    
    async def play_next(self, ctx: commands.Context):
        try :
            if not ctx.voice_client:
                return
            
            voice_client = ctx.voice_client
            if not queue:
                await ctx.send("Queue is empty!")
                
                # remove current bot status
                try:
                    await self.bot.change_presence(activity=discord.Activity(state=discord.ActivityType.playing, name="Your Mom"))
                except Exception as e:
                    print(f"Error removing bot status: {e}")
                    pass
                return
            
            song = queue.pop(0)
            url = song['url']
            title = song['title']
            thumbnail = song['thumbnail']
            channel_thumbnails = song['channel_thumbnails']
            channel_name = song['channel_name']
            channel_url = song['channel_url']
            duration = song['duration']
            view_count = song['view_count']
            
            self.current_song = {
                'title': title,
                'channel_name': channel_name,
                'url': url
            }
            
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

            try:
                gid = ctx.guild.id if ctx.guild else None
                if gid:
                    vid = song.get('video_id', '')
                    if vid:
                        lst = self.recent_played.get(gid, [])
                        lst.append({'id': vid, 'title': title, 'channel_id': song.get('channel_id'), 'channel_name': channel_name})
                        self.recent_played[gid] = lst[-20:]

                    if self.autoplay.get(gid, False) and len(queue) < 3:
                        await self.add_autoplay_suggestions(ctx, gid, count=5)
            except Exception as e:
                print(f"Error handling autoplay post-play: {e}")
        except Exception as e:
            await ctx.send(f"Failed to send Embed : {e}")
        
        headers = {
            "authority": "www.google.com",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "max-age=0",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            'sec-ch-ua': '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
            'sec-ch-ua-platform': 'Windows',
            'sec-ch-ua-platform-version': '15.0.0',
        }

        ydl_opts = {
            'format': 'bestaudio[ext=m4a]',
            'quiet': True,
            'no_warnings': True,
            'headers' : headers
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    audio_url = info['url']  # Direct stream URL
                    print(audio_url)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    await ctx.send(f"Error fetching audio, retrying... ({attempt+1}/{max_retries})")
                    continue
                else:
                    await ctx.send(f"Failed to fetch audio after {max_retries} attempts: {str(e)}")
                    return
                
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -b:a 96k'
        }
        try:
            source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
        except Exception as e:
            await ctx.send(f"Failed to play : {e}")
        
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
            await ctx.send(f"Failed to play using voice client : {e}")
            
    @commands.hybrid_command()
    async def custom_status(self, ctx: commands.Context):
        """Set a custom status for the bot."""
        try:
            # set bot activity to listening to current song
            activity_assets = {
                'large_image': 'Large Image',
                'large_text': 'Large Text',
                'small_image': 'Small Image',
                'small_text': 'Small Text',
                'small_url' : 'https://i.pinimg.com/1200x/e3/0b/d6/e30bd65b5a0087312259b40fbb2127e6.jpg',
                'large_url' : 'https://i.pinimg.com/1200x/e3/0b/d6/e30bd65b5a0087312259b40fbb2127e6.jpg'
            }
            activity = discord.Activity(type=discord.ActivityType.listening, name='Custom Status Test', assets=activity_assets, details=f"Uploaded By: {ctx.author.name}")
            await self.bot.change_presence(activity=activity)
        except Exception as e:
            await ctx.send(f"Failed to set custom status : {e}")
        
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
        
        if not song_query:
            if not queue and not hasattr(self, '_current_song'):
                await ctx.send("Please provide a song name, or play a song first.")
                return
            if hasattr(self, '_current_song'):
                song_query = self._current_song.get('title', '')
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
        if not queue:
            await ctx.send("The queue is empty.")
            return
        
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue))
        await ctx.send(f"Current queue:\n{queue_list}")
        
    @commands.hybrid_command()
    async def clear_queue(self, ctx: commands.Context):
        """Clear current queue"""
        global queue
        queue.clear()
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
        global queue
        if not queue:
            await ctx.send("The queue is empty.")
            return
        
        index = index - 1
        if index < 0 or index >= len(queue):
            await ctx.send(f"Invalid index. Use a number between 1 and {len(queue)}.")
            return
        
        removed_song = queue.pop(index)
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
        global queue
        if ctx.voice_client:
            queue.clear() 
            ctx.voice_client.stop()
            
            # remove current activity
            try:
                await self.bot.change_presence(activity=discord.Activity(state=discord.ActivityType.playing, name="Your Mom"))
            except Exception as e:
                print(f"Error removing bot status: {e}")
                pass
            
            await ctx.send("Stopped")
        else:
            await ctx.send("Nothing to stop")