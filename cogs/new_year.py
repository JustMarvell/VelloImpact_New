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
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel = None
        self.autoplay = {}
        self.disconnect_tasks = {}
            
    # Send a "Happy new year!" message in the selected channel
    @commands.hybrid_command()
    @app_commands.describe(channel="The channel to send the message in")
    async def send_new_year_message(self, ctx: commands.Context, channel: discord.TextChannel | discord.VoiceChannel):
        """ Send a Happy New Year message in the selected channel """
        
        messages = [
            'Happy New Year! Let\'s make 2026 as unforgettable as the last few years of our adventures!',
            'Cheers to an amazing 2026, sis! Seeing you go after your dreams fills me with pride, and I know this year will bring even more incredible accomplishments your way.',
            'I\'m so grateful for our friendship, and I hope the year ahead brings even more opportunities for it to grow, strengthen, and blossom in beautiful ways.',
            'We\'ve had the best time together this year. Hopefully, the coming year has more fun and adventures in store for us.',
            '2026: The year we finally become the best versions of ourselves (or at least, try to). Let\'s go!',
            'Another year closer to achieving your dreams. May this year be everything you wish for and more!',
            'Out with the old, in with the new! A very Happy New Year to you!',
            'You lived the good life last year, but this year I hope you live your best life! You deserve it! ',
        ]
        
        embed_images = [
            "https://i.pinimg.com/1200x/43/88/07/438807afafc145bbce82206d271b7c7c.jpg",
            "https://i.pinimg.com/1200x/61/15/38/611538a9a5556f97c006b19e8746da7f.jpg",
            "https://i.pinimg.com/736x/b1/9b/1f/b19b1f06b3d995b756cde8bf7df66eda.jpg",
            "https://i.pinimg.com/1200x/5a/33/e3/5a33e32bbc440c5f8be62a22524a4154.jpg",
            "https://i.pinimg.com/736x/c4/b5/b0/c4b5b0b7a0781ba03f070eee8334629b.jpg"
        ]
        
        selected_message = random.choice(messages)
        selected_image = random.choice(embed_images)
        
        try:
            embed_msg = discord.Embed(
                color=11638022,
                title="🎀.｡.:* ☆::. **_HAPPY NEW YEAR 2026_** .::.☆*.:｡.🎀",
                description="*ੈ✩‧₊˚༺☆༻*ੈ✩‧₊˚",
            )
            embed_msg.set_image(url=selected_image)
            embed_msg.set_footer(
                text="This automated message is brought to you by [/] BUFF_VelloImpact Bot",
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
            
            await channel.send(embed=embed_msg)
            
        except Exception as e:
            await ctx.send(f"Failed to send message in {channel.mention}: {str(e)}", ephemeral=True, delete_after=5)
         
    # TODO : make this command only available in this guild : 1453320275864322171
    @commands.command(guild=discord.Object(id=1453320275864322171))
    async def send_private_new_year_message(self, ctx: commands.Context, *, guild: discord.Guild):
        """ Send a Happy New Year Message to all member of a guild """
        target_guild = guild
        
        if not target_guild.members:
            await ctx.send(f"❌ No members found in {target_guild.name}. This might be due to privacy settings.", ephemeral=True)
            return
            
        await ctx.send(f"Sending message to {len(target_guild.members)} members in {target_guild.name}.....", ephemeral=True)
        
        messages = [
            'Happy New Year! Let\'s make 2026 as unforgettable as the last few years of our adventures!',
            'Cheers to an amazing 2026, sis! Seeing you go after your dreams fills me with pride, and I know this year will bring even more incredible accomplishments your way.',
            'I\'m so grateful for our friendship, and I hope the year ahead brings even more opportunities for it to grow, strengthen, and blossom in beautiful ways.',
            'We\'ve had the best time together this year. Hopefully, the coming year has more fun and adventures in store for us.',
            '2026: The year we finally become the best versions of ourselves (or at least, try to). Let\'s go!',
            'Another year closer to achieving your dreams. May this year be everything you wish for and more!',
            'Out with the old, in with the new! A very Happy New Year to you!',
            'You lived the good life last year, but this year I hope you live your best life! You deserve it! ',
        ]
        
        embed_images = [
            "https://i.pinimg.com/1200x/43/88/07/438807afafc145bbce82206d271b7c7c.jpg",
            "https://i.pinimg.com/1200x/61/15/38/611538a9a5556f97c006b19e8746da7f.jpg",
            "https://i.pinimg.com/736x/b1/9b/1f/b19b1f06b3d995b756cde8bf7df66eda.jpg",
            "https://i.pinimg.com/1200x/5a/33/e3/5a33e32bbc440c5f8be62a22524a4154.jpg",
            "https://i.pinimg.com/736x/c4/b5/b0/c4b5b0b7a0781ba03f070eee8334629b.jpg"
        ]
        msg_sent = 0
        msg_failed = 0
        
        # Filter out bots and the bot itself
        valid_members = [member for member in target_guild.members if not member.bot or member != self.bot.user]
        
        if not valid_members:
            await ctx.send(f"❌ No valid members found in {target_guild.name} to send messages to.", ephemeral=True)
            return
        
        # Process members in smaller batches to avoid rate limiting
        batch_size = 10
        for i in range(0, len(valid_members), batch_size):
            batch = valid_members[i:i + batch_size]
            
            for member in batch:
                try:
                    # Create a fresh embed for each member with random content
                    selected_message = random.choice(messages)
                    selected_image = random.choice(embed_images)
                    
                    embed_msg = discord.Embed(
                        color=11638022,
                        title="🎀.｡.:* ☆::. **_HAPPY NEW YEAR 2026_** .::.☆*.:｡.🎀",
                        description="*ੈ✩‧₊˚༺☆༻*ੈ✩‧₊˚",
                    )
                    embed_msg.set_image(url=selected_image)
                    embed_msg.set_footer(
                        text="This automated message is brought to you by [/] BUFF_VelloImpact Bot",
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
                    
                    # Try to send DM
                    await member.send(embed=embed_msg)
                    msg_sent += 1
                    
                    # Rate limiting
                    await asyncio.sleep(2)  # 2 second delay between messages
                    
                except discord.Forbidden:
                    # User has DMs disabled or blocked the bot
                    msg_failed += 1
                    cogs_logger.debug(f"Cannot send DM to {member} - likely has DMs disabled")
                except discord.HTTPException as e:
                    # Rate limit or other HTTP error
                    if e.status == 429:  # Rate limited
                        await asyncio.sleep(60)  # Wait 1 minute for rate limit
                        msg_failed += 1
                    else:
                        msg_failed += 1
                        cogs_logger.warning(f"HTTP error sending DM to {member}: {str(e)}")
                except Exception as e:
                    # Other errors
                    msg_failed += 1
                    cogs_logger.warning(f"Failed to send Christmas message to {member}: {str(e)}")
            
            # Longer delay between batches
            if i + batch_size < len(valid_members):
                await asyncio.sleep(10)  # 10 second delay between batches
                
        await ctx.send(f"✅ **Messages Sent!**\n📨 **Successful:** {msg_sent} members\n❌ **Failed:** {msg_failed} members\n📍 **Guild:** {target_guild.name}\n\n **Happy New Year!**", ephemeral=True)
