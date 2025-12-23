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

# Add this at the top with other imports
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

cogs_logger = settings.logging.getLogger("cogs")

async def run_in_thread(fn, *args, **kwargs):
    """Helper to safely run blocking functions in a thread"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, fn, *args, **kwargs)

async def setup(bot: commands.Bot) :
    await bot.add_cog(Christmas(bot))

class Christmas(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self.autoplay = {}
        self.disconnect_tasks = {}
        
    async def get_audio_source(self, song_url: str):
        """ Extract direct audio URL using yt_dlp in a thread to avoid blocking the async loop """
        
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
    
    # join a voice channel, stop current audio if any, search the song "All I want for christmas is you" and play, after playing, send a "Merry Christmas!" message in the current channel"
    @commands.hybrid_command()
    async def christmas(self, ctx: commands.Context):
        """ You know it's time!! 🎄🎶 """

        try:
            await ctx.defer()
        except:
            pass
        
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You need to be in a voice channel to use this command.")
            return
        
        voice_channel = ctx.author.voice.channel
        
        try:
            if ctx.voice_client is None:
                await voice_channel.connect()
            elif ctx.voice_client.channel != voice_channel:
                await ctx.voice_client.move_to(voice_channel)
            
            await ctx.send("You know it's time!! 🎄🎶")
        except Exception as e:
            await ctx.send(f"Failed to start the christmas party, please try again later", ephemeral=True, delete_after=5)
            return
        
        # Stop any current audio
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        song_url = "https://www.youtube.com/watch?v=aAkMkVFwAoo"  # URL for "All I Want for Christmas Is You"
        
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        
        try:
            audio_source_url = await self.get_audio_source(song_url)
            audio_source = discord.FFmpegPCMAudio(audio_source_url)
            
            ctx.voice_client.play(audio_source, after=lambda e: print(f"Finished playing: {e}"))
            
            await ctx.send("⋆⁺₊❅. Merry Christmas! *ੈ🎄✩‧₊")
        except Exception as e:
            await ctx.send(f"An error occurred while trying to play the song: {str(e)}")
            
    # Send a "Merry Christmas!" message in the selected channel
    @commands.hybrid_command()
    @app_commands.describe(channel="The channel to send the Christmas message in")
    async def send_christmas_message(self, ctx: commands.Context, channel: discord.TextChannel | discord.VoiceChannel):
        """ Send a Merry Christmas message in the selected channel """
        
        try:
            await channel.send("‧₊˚🎄✩ ₊˚⊹♡ Merry Christmas! 🎄🎶")
            await ctx.send(f"Sent a Merry Christmas message in {channel.mention}!", ephemeral=True, delete_after=5)
        except Exception as e:
            await ctx.send(f"Failed to send message in {channel.mention}: {str(e)}", ephemeral=True, delete_after=5)