from discord.ext import commands
from discord import app_commands
import controllers.randoms as rc
import discord

async def setup(bot : commands.Bot):
    await bot.add_cog(mothy(bot))

class mothy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # prank commands (for fun)
    # fake spam commands
    @commands.hybrid_command()
    async def smot(self, ctx : commands.Context, amt : int, msg : str):
        """ Spam a message """
        
        await ctx.send(ctx.author.mention + " KONTOL")
    
    # prank commands (for fun)
    # real spam commands 
    @commands.hybrid_command()
    @app_commands.describe(amt="Amount of messages to send", msg="The message to send", delay="Delay between messages (in seconds)")
    async def tmos(self, ctx : commands.Context, amt : int, msg : str, delay : float = 0.5):
        """ Spam a message with a hashtag """
        
        # check user role if it is allowed to use this command
        if (not any(role.id == 1440964380849213540 for role in ctx.author.roles)):
            await ctx.send("You don't have permission to use this command.", ephemeral=True)
            return
        
        if amt > 50 and ctx.author.id != 793122529673871360:
            await ctx.send("Kebanyakan anjing. " + ctx.author.mention + " kontol")
            return
            
        resmsg = msg
        
        for _ in range(amt):
            await ctx.send(resmsg)
            await rc.async_wait(delay)
            
    # prank commands (for fun)
    # spam dm commands
    # spam only accesible by a whitelisted user
    @commands.hybrid_command()
    @app_commands.describe(member="The member to spam", amt="Amount of messages to send", msg="The message to send", delay="Delay between messages (in seconds)")
    async def dmos(self, ctx : commands.Context, member : discord.Member, amt : int, msg : str, delay : float = 0.5):
        """ Spam a message to a member """
        
        # check user role if it is allowed to use this command
        if (not any(role.id == 1440964380849213540 for role in ctx.author.roles)):
            await ctx.send("You don't have permission to use this command.", ephemeral=True)
            return
        
        if amt > 50 and ctx.author.id != 793122529673871360:
            await ctx.send("Kebanyakan anjing. " + ctx.author.mention + " kontol")
            return
            
        resmsg = msg
        
        await ctx.send(f"Sending {amt} messages to {member.display_name}...", ephemeral=True)
        
        for _ in range(amt):
            await member.send(resmsg)
            # add a small delay to avoid rate limit
            await rc.async_wait(delay)