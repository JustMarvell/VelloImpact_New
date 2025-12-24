import ipsum
import discord
from discord.ext import  commands
from controllers import character_chunk
import asyncio
import requests
import io

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
            
    @commands.hybrid_command()
    async def generate_qr_code(self, ctx: commands.Context, *, content: str | None, size: int = 200):
        """ Generate a QR code from a given text 
        Args:
            content (text) : The content for the QR code (can be a text or a link)
            size (100 - 600): The size of the QR code image. (default = 200)
        """
        
        try:
            await ctx.defer()
        except Exception:
            pass
        
        if not content or content.strip() == "":
            await ctx.send("Please provide a text for the QR code!", ephemeral=True)
            return
        
        # Validate size parameter
        if size < 100 or size > 600:
            await ctx.send("Size must be between 100 and 1000 pixels!", ephemeral=True)
            return
        
        BASE_URL = 'https://api.qrserver.com/v1/create-qr-code'
        
        try:
            # this api will return an image of the qr code
            response = requests.get(f"{BASE_URL}?data={content}&size={size}x{size}")

            if response.status_code != 200:
                await ctx.send(f"Something wrong when fetching the response! Return Code : {response.status_code}")
                return
            
            # Create a BytesIO object from the image data
            image_bytes = io.BytesIO(response.content)
            image_bytes.seek(0)
            
            # Create discord.File object from the image data
            discord_file = discord.File(image_bytes, filename="qr_code.png")
            
            # send the image result
            await ctx.send("Here's your QR code!", file=discord_file)
            
        except Exception as e:
            await ctx.send(f"An error occurred while generating the QR code: {e}", ephemeral=True)

        

        
