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
import random
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
            
    @commands.hybrid_command()
    async def send_private_christmas_message(self, ctx: commands.Context, *, guild: discord.Guild):
        """ Send a Merry Christmas message to all member of a guild """
        await ctx.send(f"Sending message to {guild.member_count} members in {guild.name}.....")
        
        christmas_messages = {
            'Wishing you all the magic and joy this season brings—Merry Christmas!',
            'Merry Christmas my friend! Wishing you a day full of love, peace, and happiness!',
            'Wishing you a season that\'s merry and bright with the light of God\'s love.',
            'May God fill your life with love, joy, and peace this Christmas and throughout the New Year.',
            'Thank you for everything you\'ve done for me this year. Here\'s to more friendship next year!',
            'The best gift is having you for a friend. Happy Holidays!',
            'Looking forward to many more adventures with you in the New Year, my friend!',
            'May the magic of Christmas fill your home with joy and your heart with love. ',
            'May you find yourself surrounded by moments that remind you how loved you are.',
            'May this season remind you that joy isn\'t found — it\'s made.',
            'Wishing you a Christmas that feels like coming home — no matter where you are.',
            'Wishing you laughter that echoes, peace that abides, and love that never fades.',
            'May the Christmas season bring you and your family only happiness and joy.',
            'May all that is beautiful, meaningful, and brings you joy be yours this holiday season and throughout the coming year!',
            'Merry Christmas! I hope you receive one blessing after another this coming year.',
            'Though you\'re walking a challenging road, may this Christmas bring you friends who carry part of the load.',
            'Wishing you the gentleness of friends, the warmth of memories, and the promise of brighter days.',
            'Through the darkest of winters, may the light of hope shine for you this Christmas.',
            'You\'ve had more than your share of challenges this year. Wishing you peace and hope at Christmas and a new year full of better days.',
            '"Christmas will always be as long as we stand heart to heart and hand in hand." —Dr. Seuss' ,
            'This Christmas is a good time to remember that what really matters is the people next to us. That we don\'t need big things to be happy, just good times.',
            'Sometimes we forget, but the real magic of these holidays is in those small gestures that don\'t cost money: a phone call, a visit, a smile.',
            'Christmas gives us the perfect excuse to stop for a moment and appreciate what we have. May this festive season find us grateful and generous.',
            'Happy Holidays! I hope the new year comes with many good things for you and your family',
            'Merry Christmas. I hope you spend a peaceful and pleasant holiday season with your loved ones'
        }
        
        embed_images = {
            "https://i.pinimg.com/1200x/d0/4f/c2/d04fc2d1ae9a518aeb3660a80c68dec3.jpg",
            "https://i.pinimg.com/1200x/a8/df/f7/a8dff76f274d71d663180999ff26db8f.jpg",
            "https://i.pinimg.com/736x/01/38/31/013831bb17f4fe32dcac0510cddc1e4b.jpg",
            "https://i.pinimg.com/736x/10/87/6d/10876dfa73d7a870042b5159aaea416c.jpg",
            "https://i.pinimg.com/736x/67/7b/9e/677b9ed2a16304ba455b1f6b9ea92a7d.jpg"
        }

        selected_message = random.choice(christmas_messages)
        selected_image = random.choice(embed_images)
        
        embed_msg = discord.Embed(
            color=16253442,
            title="‧₊˚🎄✩ ₊˚⊹♡ Merry Christmas! ♡ ⊹˚₊ ✩🎄˚₊‧",
            description="────୨ৎ────────⋆꙳•❅*🎄*❆•꙳⋆────୨ৎ────",
        )
        embed_msg.set_image(url=selected_image)
        embed_msg.set_footer(
            text="This message is brought to you by [/] BUFF_VelloImpact Bot",
            icon_url="https://i.pinimg.com/736x/89/13/85/8913858da1aa446f87efe425e1074f16.jpg",
        )
        embed_msg.add_field(
            name=" ",
            value=selected_message,
            inline=False,
        )
        embed_msg.add_field(
            name=" ",
            value=" ",
            inline=False,
        )
        msg_sent = 0
        
        for member in guild.members:
            try:
                await member.send(embed=embed_msg)
                msg_sent += 1
                asyncio.sleep(1)
            except Exception as e:
                await ctx.send(f"Failed to send messages to {member} : {e}")
                pass
                
        await ctx.send(f"Messages sent to {msg_sent} members in {guild.name}. Merry Christmas!")