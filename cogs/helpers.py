import ipsum
import discord
from discord.ext import  commands
from controllers import character_chunk
import asyncio

model = ipsum.load_model("en")

async def setup(bot: commands.Bot):
    await bot.add_cog(Helper(bot))

class Helper(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @commands.hybrid_command()
    async def generate_random_words(self, ctx: commands.Context, *, paragraph: int):
        """ generates a random paragraph of words
        Args:
             paragraph (int): the number of words to generate
        """
        
        try:
            paragraph_result = model.generate_paragraphs(paragraph)
        except Exception as e:
            await ctx.send(f"Error when generating the paragraph : {e}")
            return
        
        for p in paragraph_result:
            try:
                await ctx.send(f"{p}")
                await asyncio.sleep(0.5)
            except Exception as e:
                await ctx.send(f"Error when sending the next paragraph, canceling proses : {e}")
                break