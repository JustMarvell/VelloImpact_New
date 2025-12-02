from discord.ext import commands
from discord import app_commands
import controllers.randoms as rc
import discord

async def setup(bot : commands.Bot):
    await bot.add_cog(mothy(bot))

class mothy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # Added
    @commands.hybrid_command()
    async def smot(self, ctx : commands.Context, amt : int, msg : str):
        """ Return a random youtube video """
        
        await ctx.send(ctx.author.display_name + " KONTOL")
            
    @commands.hybrid_command()
    async def tmos(self, ctx : commands.Context, amt : int, msg : str, hastag : str):
        """ Return a random youtube video """
        
        if amt > 20 and ctx.author.id != 793122529673871360:
            await ctx.send("Kebanyakan anjing. " + ctx.author.display_name + " kontol")
            return
        
        if hastag is not None:
            restag = "#" + hastag
            
        resmsg = msg + " " + restag
        
        for _ in range(amt):
            await ctx.send(resmsg)