import discord
from discord.ext import commands
from discord import app_commands
from youtubesearchpython import VideosSearch
import yt_dlp

async def setup(bot : commands.Bot):
    await bot.add_cog(Music(bot))

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
        if ctx.voice_client:
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

        await ctx.send(f'Playing : {title}')

        # Extract direct audio stream URL with yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url'] # Direct stream URL
            
        # Play audio
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        source = discord.FFmpegPCMAudio(audio_url, **ffmpeg_options)
        voice_client.play(source)
        
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
        if ctx.voice_client:
            ctx.voice_client.stop()
            await ctx.send('Stopped')
        else:
            await ctx.send('Nothing to stop')