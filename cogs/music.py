import discord
from discord.ext import commands
from discord import app_commands
import settings
from youtubesearchpython import Channel
import controllers.music as music_helper

# logger
cogs_logger = settings.logging.getLogger("cogs")

# cache
search_cache = {}
url_cache = {}

# =========================== Bot's Setup =======================
async def setup(bot : commands.Bot):
    await bot.add_cog(Music(bot))
    
# =========================== Helper Function =========================
def log_info(msg: str) -> None:
    """ Send a log info message
    Args:
         msg (str): Info message
    """
    cogs_logger.info(msg)

def log_error(msg: str) -> None:
    """ Send a log Error message
    Args:
         msg (str): Error message
    """
    cogs_logger.error(msg)
    
def log_warning(msg: str) -> None:
    """ Send a log Warning message
    Args:
         msg (str): Warning message
    """
    cogs_logger.warning(msg)

# ============================== MUSIC CONTROLS ========================
#
# class MusicControls(discord.ui.View):
#     def __init__(self, cog):
#         super().__init__(timeout=None) # Persisent view
#         # Keep a reference to the Music cog so the button can toggle autoplay
#         self.cog = cog
#         
#     @discord.ui.button(label="⏸", style=discord.ButtonStyle.primary)
#     async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if not interaction.guild.voice_client:
#             await interaction.response.send_message("Not in a voice channel", ephemeral=True)
#             return
#         
#         try:
#             voice_client = interaction.guild.voice_client
#             if voice_client.is_playing():
#                 voice_client.pause()
#                 self.pause_button.disabled = True
#                 self.resume_button.disabled = False
#                 await interaction.response.edit_message(view=self)
#                 await interaction.response.send_message(f"Paused!", ephemeral=True, delete_after=5)
#             else:
#                 await interaction.response.send_message("Nothing is playing", ephemeral=True)
#         except Exception as e:
#             cogs_logger.warning(f"Failed in [UI] pause_button : {e}")
# 
#     @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, disabled=True)
#     async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if not interaction.guild.voice_client:
#             await interaction.response.send_message("Not in a voice channel", ephemeral=True)
#             return
#         
#         try:
#             voice_client = interaction.guild.voice_client
#             if voice_client.is_paused():
#                 voice_client.resume()
#                 self.pause_button.disabled = False
#                 self.resume_button.disabled = True
#                 await interaction.response.edit_message(view=self)
#                 await interaction.response.send_message(f"Resumed!", ephemeral=True, delete_after=5)
#             else:
#                 await interaction.response.send_message("Not paused", ephemeral=True)
#         except Exception as e:
#             cogs_logger.warning(f"Failed in [UI] resume_button : {e}")
# 
#     @discord.ui.button(label="⏭", style=discord.ButtonStyle.primary)
#     async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         if not interaction.guild.voice_client:
#             await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
#             return
#         
#         try:
#             voice_client = interaction.guild.voice_client
#             if voice_client.is_playing() or voice_client.is_paused():
#                 voice_client.stop()
#                 await interaction.response.send_message(f"Skipped!", ephemeral=True, delete_after=5)
#             else:
#                 await interaction.response.send_message("Nothing is playing to skip!", ephemeral=True)
#         except Exception as e:
#             cogs_logger.warning(f"Failed in [UI] skip_button : {e}")
# 
#     @discord.ui.button(label="⏹", style=discord.ButtonStyle.danger)
#     async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         
#         if not interaction.guild.voice_client:
#             await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
#             return
#         
#         voice_client = interaction.guild.voice_client
#         
#         guild_id = interaction.guild.id
#         self.cog.get_queue(guild_id).clear()
#         if guild_id in self.cog.current_songs:
#             del self.cog.current_songs[guild_id]
#             
#         try:
#             voice_client.stop()
#             self.pause_button.disabled = True
#             self.resume_button.disabled = True
#             self.skip_button.disabled = True
#             await interaction.response.send_message(f"Stopped!", ephemeral=True, delete_after=5)
#         except Exception as e:
#             cogs_logger.warning(f"Failed in [UI] stop_button : {e}")
#         
#         # remove current activity
#         try:
#             await self.cog.bot.change_presence(activity=discord.Game(name="Hide and Seek", platform="Closet"))
#         except Exception as e:
#             cogs_logger.warning(f"Failed to remove bot status : {e}")
#             pass
#         
#         await interaction.response.edit_message(view=self)
# 
#     @discord.ui.button(label="Autoplay: 🔴", style=discord.ButtonStyle.secondary)
#     async def autoplay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         """Toggle autoplay + auto-start music if queue is empty"""
#         guild = interaction.guild
#         if not guild:
#             await interaction.response.send_message("This only works in servers!", ephemeral=True)
#             return
# 
#         voice_client = guild.voice_client
#         if not voice_client:
#             await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)
#             return
# 
#         gid = guild.id
#         was_enabled = self.cog.autoplay.get(gid, False)
#         now_enabled = not was_enabled
#         self.cog.autoplay[gid] = now_enabled
# 
#         # Update button appearance
#         button.label = f"Autoplay: {'🟢' if now_enabled else '🔴'}"
#         button.style = discord.ButtonStyle.success if now_enabled else discord.ButtonStyle.secondary
# 
#         await interaction.response.edit_message(view=self)
#         
#         # ———————— NEW: AUTO-START MUSIC WHEN TURNING ON ————————
#         if now_enabled and not was_enabled:  # Was off → now on
#             if len(self.cog.get_queue(gid)) == 0:  # Queue is empty → let's fill it!
#                 ctx = await self.cog.bot.get_context(interaction.message)
# 
#                 # Try to base it on the last played song
#                 recent = self.cog.recent_played.get(gid, [])
#                 if recent:
#                     last_song = recent[-1]
#                     title = last_song.get('title', 'music')
#                     await interaction.followup.send("Autoplay enabled! Starting radio based on your last song...", ephemeral=True)
#                 else:
#                     title = "lofi hip hop radio beats to relax/study to"  # Classic fallback
#                     await interaction.followup.send("Autoplay enabled! Starting a chill radio...", ephemeral=True)
# 
#                 # Add 3 songs to queue using real YouTube recommendations
#                 added = await self.cog.add_autoplay_suggestions(ctx, gid, count=3)
# 
#                 if added > 0 and not voice_client.is_playing():
#                     # Force play the next song immediately
#                     try:
#                         await self.cog.play_next(ctx)
#                     except:
#                         pass  # play_next will handle errors
# 
#     @discord.ui.button(label="☰ Show Queue", style=discord.ButtonStyle.secondary)
#     async def show_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         """Show the current music queue."""
#         queue = self.cog.get_queue(interaction.guild.id)
#         
#         if not queue:
#             await interaction.response.send_message("The queue is empty.", ephemeral=True)
#             return
#         
#         queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue[:10]))
#         
#         if len(queue) > 10:
#             queue_list += f"\n... and {len(queue) - 10} more song(s)"
#         
#         await interaction.response.send_message(f"**Current Queue:**\n{queue_list}")
#         
#     # clear queue button
#     @discord.ui.button(label="🗑️ Clear Queue", style=discord.ButtonStyle.danger)
#     async def clear_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         """Clear the current music queue."""
#         guild_id = interaction.guild.id
#         self.cog.get_queue(guild_id).clear()
#         await interaction.response.send_message("Cleared the music queue.", ephemeral=True, delete_after=4)
# 
#     @discord.ui.button(label="📝 Lyrics", style=discord.ButtonStyle.secondary)
#     async def lyrics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         """Fetch and display lyrics for the currently playing song."""
#         from controllers.lyrics_fetcher import fetch_song_lyrics, is_genius_available
#         
#         if not is_genius_available():
#             await interaction.response.send_message(
#                 "❌ Lyrics feature is not available. The bot owner needs to configure the Genius API token.",
#                 ephemeral=True,
#                 delete_after=4
#             )
#             return
#         
#         guild_id = interaction.guild.id
#         if guild_id not in self.cog.current_songs:
#             await interaction.response.send_message("No song is currently playing!", ephemeral=True)
#             return
#         
#         try : 
#             tempmsg = await interaction.response.send_message(
#                 "🎵 Searching for lyrics...",
#                 ephemeral=True, delete_after=60
#             )
#             await interaction.response.defer(ephemeral=True)
#         except Exception:
#             pass
#             
#         try:
#             song = self.cog.current_songs[guild_id]
# 
#             song_title = song.get('title', '')
#             artist_name = song.get('channel_name', '')
# 
#             result = await fetch_song_lyrics(song_title, artist_name)
#             
#             if not result.get('success'):
#                 await interaction.followup.send(f"❌ {result.get('error', 'Could not fetch lyrics')}", ephemeral=True)
#                 return
#             
#             try :
#                 await interaction.delete_original_response()
#             except Exception:
#                 pass
#             
#             embed = discord.Embed(
#                 title=result['title'],
#                 description=result['artist'],
#                 url=result['url'],
#                 color=discord.Color.gold()
#             )
#             
#             lyrics_text = result['lyrics']
#             
#             # Split lyrics into chunks to fit multiple fields
#             if len(lyrics_text) <= character_chunk.MAX_FIELD_LENGTH:
#                 embed.add_field(name="Lyrics", value=lyrics_text, inline=False)
#             else:               
#                 chunks = character_chunk.get_chunk(lyrics_text)
#                 
#                 for i, chunk in enumerate(chunks):
#                     field_name = "Lyrics" if i == 0 else f"Lyrics (cont.)"
#                     embed.add_field(name=field_name, value=chunk, inline=False)
#             
#             embed.set_footer(text="Powered by Genius")
#             
#             try:
#                 await interaction.followup.send(embed=embed, ephemeral=True)
#             except Exception:
#                 message_content = f"**{result['title']}** by {result['artist']}\n\n{lyrics_text}\n\n[Full lyrics on Genius]({result['url']})"
#             
#                 if len(message_content) <= 2000:
#                     await interaction.followup.send(message_content, ephemeral=True)
#                 else:
#                     chunks = [message_content[i:i+1900] for i in range(0, len(message_content), 1900)]
#                     for chunk in chunks:
#                         await interaction.followup.send(chunk, ephemeral=True)
#         
#         except Exception as e:
#             await interaction.followup.send(f"❌ Error fetching lyrics: {str(e)}", ephemeral=True)

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
        
    @commands.Cog.listener() # DONE
    async def on_voice_state_update(self, member: discord.Member, after: discord.VoiceState):
        guild = member.guild
        voice_client = guild.voice_client

        if member == self.bot.user:
            # Bot was disconnected (e.g., by Discord idle timeout)
            if after.channel is None:
                try:
                    guild_id = guild.id
                    music_helper.get_queue(self, guild_id).clear() 
                    if guild_id in self.current_songs:
                        del self.current_songs[guild_id]
                    voice_client.stop()
                    
                    if guild.id in self.disconnect_tasks:
                        del self.disconnect_tasks[guild.id]
                        
                    log_info(f"Bot disconnected from voice channel in guild {guild.name} ({guild.id})")
                except Exception as e:
                    log_error(f"Error handling bot disconnection: {e}")
                    pass
            return

        if voice_client is None:
            return

        channel = voice_client.channel
        if len(channel.members) == 1:  # Only bot left
            if guild.id in self.disconnect_tasks:
                return  # Timer already running
            task = self.bot.loop.create_task(music_helper.disconnect_timer(self=self, guild=guild))
            self.disconnect_tasks[guild.id] = task
        else:
            # Users present: cancel any timer
            if guild.id in self.disconnect_tasks:
                self.disconnect_tasks[guild.id].cancel()
                del self.disconnect_tasks[guild.id]

    @commands.hybrid_command() # DONE
    async def arise(self, ctx : commands.Context):            
        """Join the voice channel"""
        try:
            await ctx.defer()
        except Exception(BaseException):
            pass
        
        if not ctx.author.voice:
            await ctx.send("You are not in a voice channel!", ephemeral=True, delete_after=5)
            return

        channel = ctx.author.voice.channel
        
        try:
            if ctx.voice_client is not None:
                # NEW: Handle zombie state
                check_zombie = await music_helper.handle_zombie_voice_state(ctx=ctx, channel=channel)
                if check_zombie is None:
                    return
        except Exception as e:
            await ctx.send(f"Error handling existing voice client: {e}", ephemeral=True, delete_after=10)
            log_error(f"Error handling existing voice client! Reason : {e}")
            return

        try:
            await channel.connect()
            await ctx.send(f"I've been summoned to {channel.name}")
        except Exception(BaseException) as e:
            await ctx.send(f"Failed to connect to voice channel! : {e}", ephemeral=True, delete_after=10)
            log_error(f"Failed to connect to voice channel! Reason : {e}")
            
    @commands.hybrid_command() # DONE
    async def release(self, ctx : commands.Context):
        """ Leave a voice Channel """
        guild_id = ctx.guild.id
        queue = music_helper.get_queue(self=self, guild_id=guild_id)
        if ctx.voice_client:
            queue.clear()
            self.channel = None
            
            # TODO : Change bot's presence
            # try:
            #     await self.bot.change_presence(activity=discord.Game(name="Hide and seek", platform="Closet"))
            #     # await self.bot.change_presence(activity=discord.Activity(state=discord.ActivityType.playing, name="Your Mom"))
            # except Exception as e:
            #     print(f"Error removing bot status: {e}")
            #     pass
            
            try:
                if guild_id in self.current_songs:
                    del self.current_songs[guild_id]

                await ctx.voice_client.disconnect(force=True)
                try:
                    ctx.guild.voice_client = None
                except Exception(BaseException):
                    pass
                
                if ctx.guild.id in self.disconnect_tasks:
                    del self.disconnect_tasks[ctx.guild.id]
            except Exception(BaseException) as e:
                await ctx.send(f"Error disconnecting: {e}", ephemeral=True, delete_after=5)
                pass
                
            await ctx.send('kbay', delete_after=8)
        else:
            await ctx.send("I'm not in a voice channel", ephemeral=True, delete_after=5)
    
    @commands.hybrid_command(name="play") # DONE
    @app_commands.describe(
        name="Song title to search on YouTube"
    )
    async def play(self, ctx: commands.Context, name: str = None):
        """ Search a song on YouTube and play it in a voice channel """
        try:
            await ctx.defer()
        except Exception(BaseException):
            pass
        
        try:
            # Check if user is not in a voice channel
            if not ctx.author.voice:
                await ctx.send("You need  to join a voice channel first to use me!", ephemeral=True, delete_after=5)
                return 
            
            # Check if the search querry is not empty
            if name is None:
                await ctx.send("Cannot search an empty title, Please input a valid search term!", ephemeral=True, delete_after=5)
                return 
            
            guild_id = ctx.guild.id
            queue = music_helper.get_queue(self=self, guild_id=guild_id)
            
            # Check if current queue is full
            if len(queue) >= 10:
                await ctx.send("Queue is full! Max 10 songs.", ephemeral=True, delete_after=5)
                return
            
            # Prompt to join if not connected to a voice channel
            if not ctx.voice_client:
                await ctx.send("I'm currently not connected to a voice channel. Please use ``/arise`` to summon me!", ephemeral=True, delete_after=10)
                return
            
            voice_client = ctx.voice_client
    
            if queue in search_cache:
                results = search_cache[queue]
            else:
                try:
                    results = await music_helper.video_search(query=queue, limit=1)
                    if len(search_cache) >= 50:
                        search_cache.pop(next(iter(search_cache)))
                    search_cache[queue] = results
                except Exception as e:
                    await ctx.send(f"Error searching YouTube: {str(e)}", ephemeral=True, delete_after=5)
                    log_error(f"Error raised when searching YouTube in play_music. Reason : {e}")
                    return
            
            if not results:
                await ctx.send(f'No song(s) found for {queue}', ephemeral=True, delete_after=5)
                return
                
            video = results[0]
            url = video['link']
            title = video['title']
            thumbnail = video['thumbnails'][0]['url']
            channel_id = video['channel']['id']
            channel_thumbnails = Channel.get(channel_id)['thumbnails'][0]['url']
            channel_url = Channel.get(channel_id)['url']
            channel_name = Channel.get(channel_id)['title']
            duration = music_helper.format_duration(seconds_or_str=video['duration'])
            view_count = music_helper.format_view_count(count_or_str=video['viewCount']['short'])

            video_id = music_helper.get_video_id_from_url(url) or ''
            queue.append({'url': url, 'video_id': video_id, 'title': title, 'thumbnail': thumbnail, 'channel_thumbnails': channel_thumbnails, 'channel_name': channel_name, 'channel_id': channel_id, 'duration': duration, 'view_count': view_count, 'channel_url': channel_url})

            if not voice_client.is_playing():
                await music_helper.play_next(self=self, ctx=ctx)
                await self.send_embed(ctx=ctx)
            else:
                await ctx.send(f"Added to queue: **{title}**")
        except Exception as e:
            await ctx.send(f"Something went wrong on internal play_music : {e}", ephemeral=True, delete_after=5)
    
    # TODO : FIX add autoplay suggestions
    # async def add_autoplay_suggestions(self, ctx: commands.Context, guild_id: int, count: int = 1):
    #     """Use yt_dlp to get REAL YouTube 'Up Next' / related videos for true autoplay"""
    #     try:
    #         """Fetch REAL YouTube autoplay recommendations safely in a thread"""
    #         if not ctx.guild or not ctx.voice_client:
    #             return 0
    # 
    #         recent = self.recent_played.get(guild_id, [])
    #         if not recent:
    #             return 0
    # 
    #         last_song = recent[-1]
    #         video_id = last_song.get('id') or get_video_id_from_url(last_song.get('url', ''))
    #         if not video_id:
    #             return 0
    # 
    #         # Collect IDs to avoid duplicates
    #         played_ids = {item.get('id') for item in recent if item.get('id')}
    #         queued_ids = {song.get('video_id') for song in self.get_queue(guild_id) if song.get('video_id')}
    #         avoid_ids = played_ids.union(queued_ids)
    # 
    #         def fetch_related():
    #             ydl_opts = {
    #                 'quiet': True,
    #                 'no_warnings': True,
    #                 'extract_flat': True,
    #                 'skip_download': True,
    #                 'playlistend': count + 10,  # Get extra to filter
    #             }
    #             try:
    #                 with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    #                     info = ydl.extract_info(
    #                         f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}",
    #                         download=False
    #                     )
    #                     return info.get('entries', [])[1:]  # Skip first (current song)
    #             except Exception as e:
    #                 print(f"[Autoplay] yt_dlp failed: {e}")
    #                 return []
    # 
    #         try:
    #             entries = await run_in_thread(fetch_related)
    #         except Exception as e:
    #             print(f"[Autoplay] Thread execution failed: {e}")
    #             return 0
    # 
    #         added = 0
    #         seen = set()
    # 
    #         for entry in entries:
    #             if added >= count:
    #                 break
    # 
    #             vid_id = entry.get('id')
    #             if not vid_id or vid_id in avoid_ids or vid_id in seen:
    #                 continue
    #             if entry.get('title') in ('[Private video]', '[Deleted video]'):
    #                 continue
    # 
    #             title = entry.get('title', 'Unknown')
    #             url = f"https://www.youtube.com/watch?v={vid_id}"
    #             duration = format_duration(entry.get('duration')) if entry.get('duration') else "LIVE"
    #             thumbnail = entry['thumbnails'][-1]['url'] if entry.get('thumbnails') else ''
    # 
    #             channel_name = entry.get('uploader', 'Unknown')
    #             channel_id = entry.get('channel_id')
    # 
    #             channel_thumbnails = ''
    #             channel_url = f"https://www.youtube.com/channel/{channel_id}" if channel_id else ''
    # 
    #             # Optional: enrich channel name (lightweight, async-safe)
    #             if channel_id:
    #                 try:
    #                     ch_info = await run_in_thread(Channel.get, channel_id)
    #                     channel_name = ch_info.get('title', channel_name)
    #                     if ch_info.get('thumbnails'):
    #                         channel_thumbnails = ch_info['thumbnails'][0]['url']
    #                     channel_url = ch_info.get('url', channel_url)
    #                 except:
    #                     pass
    # 
    #             self.get_queue(guild_id).append({'url': url, 'video_id': vid_id, 'title': title, 'thumbnail': thumbnail, 'channel_name': channel_name, 'channel_id': channel_id or '', 'duration': duration, 'view_count': '', 'channel_thumbnails': channel_thumbnails, 'channel_url': channel_url})
    # 
    #             seen.add(vid_id)
    #             added += 1
    # 
    #         if added > 0:
    #             try:
    #                 await ctx.send(f"Autoplay added {added} new song(s)", delete_after=5)
    #             except:
    #                 pass
    # 
    #         return added
    # 
    #     except Exception as e:
    #         print(f"Autoplay error: {e}")
    #         return 0
    # 
    # DONE
    async def send_embed(self, ctx: commands.Context):
        if not ctx.voice_client:
            return
        
        guild_id = ctx.guild.id
        queue = music_helper.get_queue(self=self, guild_id=guild_id)
        
        song = queue.pop(0)
        
        self.current_songs[guild_id] = song
        
        url = song['url']
        title = song['title']
        thumbnail = song['thumbnail']
        channel_thumbnails = song['channel_thumbnails']
        channel_name = song['channel_name']
        channel_url = song['channel_url']
        duration = song['duration']
        view_count = song['view_count']
        try :
            
            # TODO : Add UI buttons
            # view = MusicControls(self)
            # view.pause_button.disabled = False
            # view.resume_button.disabled = True
            # try:
            #     if ctx.guild:
            #         enabled = self.autoplay.get(ctx.guild.id, False)
            #         view.autoplay_button.label = f"Autoplay: {'🟢' if enabled else '🔴'}"
            #         view.autoplay_button.style = discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary
            # except Exception:
            #     pass

            embed = discord.Embed(title=f'Now Playing : ')
            embed.set_author(name=channel_name, url=channel_url)
            embed.set_thumbnail(url='https://upload.wikimedia.org/wikipedia/commons/e/ef/Youtube_logo.png')
            embed.set_footer(text=channel_name, icon_url=channel_thumbnails)
            embed.add_field(name=title, value=f'Duration : {duration}\nView Count : {view_count}')
            embed.set_image(url = thumbnail)
            
            try:
                # send discord embed
                await ctx.send(embed=embed)
                
                activity = discord.Activity(type=discord.ActivityType.listening, 
                                            name=f"🎵 {title}", 
                                            url=url,
                                            details=f"Uploaded to Youtube By: {channel_name}", 
                                            platform='YouTube', 
                                            details_url=channel_url)
                
                await self.bot.change_presence(activity=activity)
                
            except Exception as e:
                raise e
            
        except Exception as e:
            await ctx.send(f"Failed to send Embed : {e}", ephemeral=True, delete_after=5)
            log_error(f"Failed to send Embed : {e}")
                  
        try:
            if guild_id:
                vid = song.get('video_id', '')
                if vid:
                    lst = self.recent_played.get(guild_id, [])
                    lst.append({'id': vid, 'title': title, 'channel_id': song.get('channel_id'), 'channel_name': channel_name})
                    self.recent_played[guild_id] = lst[-10:]

                # TODO : FIX autoplay
                # if self.autoplay.get(guild_id, False) and len(queue) < 3:
                #     await self.add_autoplay_suggestions(ctx, guild_id, count=3)
        except Exception as e:
            print(f"Error handling autoplay post-play: {e}")
        
    # TODO : FIX Lyrics command
    # @commands.hybrid_command()
    # async def lyrics(self, ctx: commands.Context, *, song_query: str = None):
    #     """Fetch and display lyrics for a song.
    #     
    #     Usage:
    #     - /lyrics [song name and artist] - Fetch lyrics for a specific song
    #     - /lyrics - Fetch lyrics for the currently playing song
    #     """
    #     if not is_genius_available():
    #         await ctx.send(
    #             "❌ Lyrics feature is not available. The bot owner needs to set the `GENIUS_API_TOKEN` environment variable.\n"
    #             "Get a free token from: https://genius.com/api-clients"
    #         )
    #         return
    #     
    #     guild_id = ctx.guild.id
    #     
    #     if not song_query:
    #         q = self.get_queue(guild_id)
    #         if not q and guild_id not in self.current_songs:
    #             await ctx.send("Please provide a song name, or play a song first.")
    #             return
    #         if guild_id in self.current_songs:
    #             song_query = self.current_songs[guild_id].get('title', '')
    #         else:
    #             await ctx.send("Please provide a song name, or play a song first.")
    #             return
    #     
    #     try:
    #         await ctx.defer()
    #     except Exception:
    #         pass
    #     
    #     try:
    #         await ctx.send(f"🎵 Searching for lyrics for **{song_query}**...")
    #         
    #         result = await fetch_song_lyrics(song_query)
    #         
    #         if not result.get('success'):
    #             await ctx.send(f"❌ {result.get('error', 'Could not fetch lyrics')}")
    #             return
    #         
    #         embed = discord.Embed(
    #             title=result['title'],
    #             description=result['artist'],
    #             url=result['url'],
    #             color=discord.Color.gold()
    #         )
    #         
    #         lyrics_text = result['lyrics']
    #         
    #         if len(lyrics_text) <= character_chunk.MAX_FIELD_LENGTH:
    #             embed.add_field(name="Lyrics", value=lyrics_text, inline=False)
    #         else:                    
    #             chunks = character_chunk.get_chunk(lyrics_text)
    #             
    #             for i, chunk in enumerate(chunks):
    #                 field_name = "Lyrics" if i == 0 else f"Lyrics (cont.)"
    #                 embed.add_field(name=field_name, value=chunk, inline=False)
    #         
    #         embed.set_footer(text="Powered by Genius")
    #         
    #         try:
    #             await ctx.send(embed=embed)
    #         except Exception as e:
    #             message_content = f"**{result['title']}** by {result['artist']}\n\n{lyrics_text}\n\n[Full lyrics on Genius]({result['url']})"
    #             if len(message_content) <= 2000:
    #                 await ctx.send(message_content)
    #             else:
    #                 chunks = [message_content[i:i+1900] for i in range(0, len(message_content), 1900)]
    #                 for chunk in chunks:
    #                     await ctx.send(chunk)
    #     
    #     except Exception as e:
    #         await ctx.send(f"❌ Error fetching lyrics: {str(e)}")
        
    @commands.hybrid_command() # DONE
    async def show_queue(self, ctx: commands.Context):
        """Show current song queue"""
        try:
            queue_list = await music_helper.show_queue(self, ctx)
            if queue_list is not None:
                await ctx.send(f"Current queue:\n{queue_list}")
            else:
                await ctx.send("Queue is empty!", delete_after=5)
        except Exception(BaseException) as e:
            await ctx.send(f"Something went wrong when fetching queue! : {e}", ephemeral=True, delete_after=5)
        
    @commands.hybrid_command() # DONE
    async def clear_queue(self, ctx: commands.Context):
        """Clear current queue"""
        try:
            guild_id = ctx.guild.id
            music_helper.get_queue(self, guild_id).clear()
            await ctx.send(f"Queue cleared by {ctx.author.mention}", delete_after=15)
        except Exception(BaseException) as e:
            await ctx.send(f"Something went wrong when clearing the queue : {e}", ephemeral=True, delete_after=5)
        
    @commands.hybrid_command() # DONE
    async def skip(self, ctx: commands.Context):
        """Skip current song"""
        if not ctx.voice_client:
            await ctx.send("Not in a voice channel!")
            return
        
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await ctx.send("Nothing is playing to skip!")
            return
        
        try:
            ctx.voice_client.stop()
            await ctx.send(f"{ctx.author.mention} skipped current song!", delete_after=10)
        except Exception(BaseException) as e:
            await ctx.send(f"Failed to skip current song : {e}", ephemeral=True, delete_after=5)
        
    @commands.hybrid_command() # DONE
    async def remove(self, ctx: commands.Context, index: int):
        """Remove song at specified index"""
        guild_id = ctx.guild.id
        q = music_helper.get_queue(self, guild_id)
        if not q:
            await ctx.send("The queue is empty.", ephemeral=True, delete_after=5)
            return
        
        index = index - 1
        if index < 0 or index >= len(q):
            await ctx.send(f"Invalid index. Use a number between 1 and {len(q)}.", ephemeral=True, delete_after=5)
            return
        
        try:
            removed_song = q.pop(index)
            await ctx.send(f"{ctx.author.mention} removed a song from queue: {removed_song['title']}", delete_after=10)
        except Exception(BaseException) as e:
            await ctx.send(f"Something went wrong when removing the song! : {e}", ephemeral=True, delete_after=5)
        
    @commands.hybrid_command() # DONE
    async def pause(self, ctx : commands.Context):
        """Pause current song"""
        try:
            if ctx.voice_client and ctx.voice_client.is_playing():
                ctx.voice_client.pause()
                await ctx.send('Paused')
            else:
                await ctx.send('Nothing is currently playing')
        except Exception(BaseException) as e:
            await ctx.send(f"Something went wrong when pausing. Please try again later! : {e}", ephemeral=True, delete_after=5)
    
    @commands.hybrid_command() # DONE
    async def resume(self, ctx : commands.Context):
        """Resume current paused song"""
        try:
            if ctx.voice_client and ctx.voice_client.is_paused():
                ctx.voice_client.resume()
                await ctx.send('Resumed')
            else:
                await ctx.send('Not Paused')
        except Exception(BaseException) as e:
            await ctx.send(f"Something went wrong when resuming the song! : {e}")
            
    @commands.hybrid_command() # DONE
    async def stop(self, ctx : commands.Context):
        """Stop playing song"""
        try:
            if ctx.voice_client:
                guild_id = ctx.guild.id
                music_helper.get_queue(self, guild_id).clear() 
                if guild_id in self.current_songs:
                    del self.current_songs[guild_id]
                ctx.voice_client.stop()
                
                # TODO : Change bot's activity
                # remove current activity
                # try:
                #     await self.bot.change_presence(activity=discord.Game(name="Hide and seek", platform="Closet"))
                # except Exception as e:
                #     print(f"Error removing bot status: {e}")
                #     pass
                
                await ctx.send(f"{ctx.author.mention} stopped current song!", delete_after=10)
            else:
                await ctx.send("Nothing to stop", ephemeral=True, delete_after=5)
        except Exception(BaseException) as e:
            await ctx.send(f"Something went wrong when stopping the song! {e}", ephemeral=True, delete_after=5)