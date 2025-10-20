import discord
from discord.ext import commands
from discord import app_commands
from youtubesearchpython import VideosSearch
import yt_dlp

queue = []

async def setup(bot : commands.Bot):
    await bot.add_cog(Music(bot))
    
class MusicControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Presistent view
        
    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.pause()
            # Update button states
            self.pause_button.disabled = True
            self.resume_button.disabled = False
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("Paused", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing", ephemeral=True)

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.primary, disabled=True)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_paused():
            voice_client.resume()
            # update button states
            self.pause_button.disabled = False
            self.resume_button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("Resumed", ephemeral=True)
        else:
            await interaction.response.send_message("Not paused", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()  # Triggers play_next via after_playing
            await interaction.response.send_message("Skipped current song", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing to skip!", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global queue
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        queue.clear()
        voice_client.stop()
        # Disable all buttons except Stop
        self.pause_button.disabled = True
        self.resume_button.disabled = True
        self.skip_button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("Stopped", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Added
    @commands.hybrid_command()
    async def arise(self, ctx : commands.Context):
        """ Join a Voice Channel """
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            await ctx.send(f'I have been summoned to join {channel.name}')
        else:
            await ctx.send('Please join a voice channel first!')
            
    @commands.hybrid_command()
    async def release(self, ctx : commands.Context):
        """ Leave a voice Channel """
        global queue
        if ctx.voice_client:
            queue.clear()
            await ctx.voice_client.disconnect()
            await ctx.send('kbay')
        else:
            await ctx.send("I'm not in a voice channel")
    
    @commands.hybrid_command()
    async def play_music(self, ctx : commands.Context, *, querry):
        if not ctx.author.voice:
            await ctx.send('You need to join a voice channel first to use me!')
            return

        # join vc if not already
        if not ctx.voice_client:
            channel = ctx.author.voice.channel
            voice_client = await channel.connect()
        else:
            voice_client = ctx.voice_client
            
            
        # search the music in yt
        search = VideosSearch(query=querry, limit=1)
        results = search.result()['result']
        
        if not results:
            await ctx.send(f'No music found for {querry}')
            return
            
        video = results[0]
        url = video['link']
        title = video['title']
        
        queue.append({'url' : url, 'title' : title})
        
        if not voice_client.is_playing():
            # Play immediately if nothing is playing
            await self.play_next(ctx)
        else:
            # Add to queue if something is playing
            await ctx.send(f"Added to queue: {title}")
    
    async def play_next(self, ctx: commands.Context):
        if not ctx.voice_client:
            return
        
        voice_client = ctx.voice_client
        if not queue:
            await ctx.send("Queue is empty!")
            return
        
        # Get the next song
        song = queue.pop(0)
        url = song['url']
        title = song['title']
        
        # Create new view with buttons
        view = MusicControls()
        # Set initial button states based on playback
        view.pause_button.disabled = False
        view.resume_button.disabled = True
        await ctx.send(f"Now playing: {title}", view=view)
        
        # Extract direct audio stream URL with yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']  # Direct stream URL
        
        # Play audio
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
        
        # Define callback for when the song ends
        def after_playing(error):
            # Run play_next in an async context
            import asyncio
            coro = self.play_next(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, loop=self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(f"Error in play_next: {e}")
        
        voice_client.play(source, after=after_playing)
        
    @commands.hybrid_command()
    async def show_queue(self, ctx: commands.Context):
        if not queue:
            await ctx.send("The queue is empty.")
            return
        
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queue))
        await ctx.send(f"Current queue:\n{queue_list}")
        
    @commands.hybrid_command()
    async def clear_queue(self, ctx: commands.Context):
        global queue
        queue.clear()
        await ctx.send("Queue cleared.")
        
    @commands.hybrid_command()
    async def skip(self, ctx: commands.Context):
        if not ctx.voice_client:
            await ctx.send("Not in a voice channel!")
            return
        
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await ctx.send("Nothing is playing to skip!")
            return
        
        ctx.voice_client.stop()  # Triggers play_next via after_playing
        await ctx.send("Skipped current song")
        
    @commands.hybrid_command()
    async def remove(self, ctx: commands.Context, index: int):
        global queue
        if not queue:
            await ctx.send("The queue is empty.")
            return
        
        # Convert 1-based index to 0-based
        index = index - 1
        if index < 0 or index >= len(queue):
            await ctx.send(f"Invalid index. Use a number between 1 and {len(queue)}.")
            return
        
        # Remove the song
        removed_song = queue.pop(index)
        await ctx.send(f"Removed from queue: {removed_song['title']}")
        
    @commands.hybrid_command()
    async def pause(self, ctx : commands.Context):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send('Paused')
        else:
            await ctx.send('Nothing is currently playing')
    
    @commands.hybrid_command()
    async def resume(self, ctx : commands.Context):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send('Resumed')
        else:
            await ctx.send('Not Paused')
            
    @commands.hybrid_command()
    async def stop(self, ctx : commands.Context):
        global queue
        if ctx.voice_client:
            queue.clear()  # Clear queue on stop
            ctx.voice_client.stop()
            await ctx.send("Stopped")
        else:
            await ctx.send("Nothing to stop")