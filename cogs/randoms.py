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
        
    @commands.hybrid_command()
    async def quotes(self, ctx : commands.Context):
        """ Return a random quotes available from the internet """

        # Get quotes
        try :
            await ctx.defer()
        except Exception:
            pass
        
        try :
            quotes = await rc.get_random_quotes()
        except Exception as e:
            await ctx.send(f"Failed to fetch quotes : {e}", ephemeral=True)
            return
            
        await ctx.send(quotes)
        
        
    @commands.hybrid_command()
    async def roast(self, ctx : commands.Context, *, target : discord.Member):
        """ Roast a user """
        
        try :
            await ctx.defer()
        except Exception:
            pass
        
        try :
            quotes = await rc.get_random_roast()
        except Exception as e:
            await ctx.send(f"Failed to fetch roast : {e}", ephemeral=True)
            return
        
        await ctx.send(f"{target.mention}, {quotes}")
        
    @commands.hybrid_command()
    @app_commands.describe(
        question = "Question to ask the magic 8 ball"
    )
    async def magic_8_ball(self, ctx : commands.Context, *, question : str):
        """ Ask something to the magic 8 ball """
        
        try :
            await ctx.defer()
        except Exception:
            pass
        
        try :
            response = await rc.get_magic_8_ball(question=question)
        except Exception as e:
            await ctx.send(f"Failed to ask magic 8 ball : {e}", ephemeral=True)
            return
        
        q = response["question"]
        a = response["answer"]

        field = f"**Question** : {q}\n**Answer** : {a}"
        
        await ctx.send(field)
        
    @commands.hybrid_command()
    @app_commands.describe(
        prompt = "Prompt given to the bot"
    )
    async def chat(self, ctx : commands.Context, *, prompt : str):
        """ Chat with the bot """

        try :
            await ctx.defer()
        except Exception:
            pass
        
        try:
            response = await rc.get_ai_chat(prompt=prompt)
        except Exception as e:
            await ctx.send(f"Failed to connect with the AI", ephemeral=True)
            return
        
        p = response["prompt"]
        a = response["answer"]

        field = f"**Prompt** : {p}\n**Answer** : {a}"

        await ctx.send(field)
