import discord
from discord.ext import commands
from discord import app_commands
import datetime
import controllers.test as test
import random

async def setup(bot: commands.Bot) :
    await bot.add_cog(Debug(bot))
    
class Debug(commands.Cog) :
    def __init__(self, bot) :
        self.bot = bot
                
    bad_ping = 15606812
    medium_ping = 15134236
    good_ping = 2420252
    
    # "Large image key" : "Large image text"
    image_asset_key = [
        "ayla_kuning",
        "absolute_idiot",
        "cat_think",
        "speed"
    ]
        
    @commands.hybrid_command()
    async def ping(self, ctx : commands.Context):
        """Ping the bot"""
        
        ping = round(self.bot.latency * 1000)
        # ping_color = 000000
        embed = discord.Embed(title="PING THE BOT", description=f"ping succesfull with result : {ping}ms")
        # check if bad, medium, or good ping
        if ping < 250:
            ping_color = self.good_ping
        elif ping < 350:
            ping_color = self.medium_ping
        else:
            ping_color = self.bad_ping
            
        embed.color = ping_color
        await ctx.send(embed=embed)

    # set bot's custom status (only accesible by bot owner)
    @commands.hybrid_command()
    @app_commands.describe(activity_type="Type of activity", activity_name="Name of the activity")
    async def custom_status(self, ctx: commands.Context, *, activity_type : discord.ActivityType, activity_name : str):
        """Set a custom status for the bot."""
        
        if (activity_type == None):
            await ctx.send("Failed : Can't have NoneType activity", ephemeral=True)
            return
        
        # choose random image asset
        asset = {
            'large_image': random.choice(self.image_asset_key)
        }
        
        try:
            activity = discord.Activity(type=activity_type, name=activity_name, details=f"Uploaded By: {ctx.author.name}", assets=asset)
            await self.bot.change_presence(activity=activity)
            await ctx.send("Succesfully changed the bot's status!", ephemeral=True)
            
        except Exception as e:
            await ctx.send(f"Failed to set custom status : {e}")

        # make the bot say a message (not reply to command message)
    @commands.hybrid_command()
    async def say(self, ctx : commands.Context, *, message : str, channel: discord.TextChannel | discord.VoiceChannel):
        """ Make the bot say a message in a selected channel
        Args:
            message: message to be sent
            channel: selected channel
        """
        try:
            await channel.send(message)
            await ctx.send(f"Message sent to {channel.name}", ephemeral=True, delete_after=10)
            
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", ephemeral=True)
        