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
    async def say_hello(self, ctx : commands.Context):
        await ctx.send("hello!")
        
    @commands.hybrid_command()
    async def start(self, ctx : commands.Context):
        """Initialize the bot"""
        embed = discord.Embed(title="VelloImpact", description="Check status")
        
        embed.add_field(name="/list_commands", value="")
        
        embed.set_image(url='https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTem7GDm343HtC1hOABYFfEWFrSTwyfmpDt8A&s')
        
        embed.set_footer(text="session date")
        embed.timestamp = discord.utils.utcnow()
        
        await ctx.send(embed=embed)
        
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
        
    @commands.hybrid_command()
    async def list_commands(self, ctx : commands.Context):
        """List all commands"""
        embed = discord.Embed(title="EGG INCUBATOR", description="command list :", color=14706181)
        
        embed.add_field(name="/list_commands", value="list all commands", inline=False)
        embed.add_field(name="/check_temp", value="measure the temperature inside the incubator", inline=False)
        embed.add_field(name="/check_humidity", value="measure the humidity inside the incubator", inline=False)
        embed.add_field(name="/toggle_light [status/on/off]", value="toggle the light based on input\n- status : Get the current state of the light (on/off)\n- on : Turn on the light\n- off : Turn off the light", inline=False)
        embed.add_field(name="/take_photo", value="take pictures of the current conditions inside the incubator", inline=False)
        
        embed.set_footer(text="session date")
        embed.timestamp = discord.utils.utcnow()
        
        await ctx.send(embed=embed)
        
    @commands.hybrid_command()
    async def get_name(self, ctx : commands.Context, action: str = None):
        await ctx.send("Wait for testing...")
        
        if action is None:
            await ctx.send("No character name given")
        else:
            data = await test.get_character(action)
            
            await ctx.send(data)
            
    @commands.hybrid_command()
    async def put_test(self, ctx : commands.Context):
        await test.put_character()
        await ctx.send("Put test character")