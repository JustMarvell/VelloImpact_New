import discord
from discord.ext import commands
from discord import app_commands
import datetime
import controllers.test as test

async def setup(bot: commands.Bot) :
    await bot.add_cog(Debug(bot))
    
class Debug(commands.Cog) :
    def __init__(self, bot) :
        self.bot = bot
        
    @commands.hybrid_command()
    async def say_hello(self, ctx : commands.Context, action: str):
        await ctx.send(action)
        
    bad_ping = 15606812
    medium_ping = 15134236
    good_ping = 2420252
        
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
        