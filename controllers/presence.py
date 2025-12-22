import discord
from discord import app_commands
from discord.ext import commands

async def change_presence(bot: commands.Bot , cog: commands.Cog, activity_type : discord.ActivityType, activity: str) -> None:
    """ Change discord bot presence status """
    if cog:
        await cog.bot.change_presence(activity=discord.Activity(type=activity_type, name=activity))
    elif bot:
        await bot.change_presence(activity=discord.Activity(type=activity_type, name=activity))
    else:
        raise Exception("No cogs or bot base class provided!")