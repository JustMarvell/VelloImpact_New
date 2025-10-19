from discord.ext import commands
from discord import app_commands
import controllers.randoms as rc
import discord

async def setup(bot : commands.Bot):
    await bot.add_cog(Randoms(bot))

class Randoms(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Added
    @commands.hybrid_command()
    async def get_random_video(self, ctx : commands.Context):
        """ Return a random youtube video """
        
        url = await rc.get_random_video()
        
        await ctx.send(url)
        
    @commands.hybrid_command()
    async def get_random_music_video(self, ctx : commands.Context):
        """ Return a random youtube music video """
        
        url = await rc.get_random_music()
        
        await ctx.send(url)