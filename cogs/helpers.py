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
    
class DictionaryHelperUI(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.cog = cog
        
    @discord.ui.button(label="Source", emoji="📖", style=discord.ButtonStyle.link)
    async def audio_link_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print("pressed")

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
            
    @commands.hybrid_command()
    async def dictionary(self, ctx: commands.Context, *, word: str | None):
        """ Find the meaning of the word in the dictionary 
        Args:
            word: The specified word
        """
        try:
            await ctx.defer()
        except Exception:
            pass
        
        if not word or word.strip() == "":
            await ctx.send("Please provide a word!", ephemeral=True)
            return

        BASE_URL = 'https://api.dictionaryapi.dev/api/v2/entries/en/'
        
        try:
            response = requests.get(f"{BASE_URL}{word}")
            
            if response.status_code == 404:
                await ctx.send(f"{word} is not a valid word!")
                return
            elif response.status_code != 200:
                await ctx.send(f"Something wrong when fetching the response! Return Code : {response.status_code}")
                return
            
        except Exception as e:
            await ctx.send(f"An error occured when getting response : {e}", ephemeral=True)
            return
        
        result = response.json()[0]
        res_word = result.get('word')
        res_phonetic = result.get('phonetic')
        res_meanings = result.get('meanings')
        res_source_url = result.get('sourceUrls')[0]
        # prioritize us version (1 : us, 0 : uk)
        try:
            try:
                res_phonetic_sound = result.get('phonetics')[1]['sourceUrl']
            except Exception:
                res_phonetic_sound = result.get('phonetics')[0]['sourceUrl']
        except Exception:
            res_phonetic_sound = None
        try:
            embed = discord.Embed(
                color=2925340,
                title="Here's a definition for that word!",
                description=f"**Word** : {res_word}\n**Phonetic** : {res_phonetic}",
            )
            embed.set_footer(
                text="Response provided by dictionaryapi.dev",
            )
            
            def_text = ""
            for meanings in res_meanings:
                for definition in meanings['definitions'][0:2]:
                    def_text += definition['definition']
                embed.add_field(
                    name=f"{meanings['partOfSpeech'].capitalize()} : ",
                    value=f"> - {def_text}",
                    inline=False,
                )
            
            view = discord.ui.View(timeout=None)
            
            url_source_button = discord.ui.Button(label="Source", style=discord.ButtonStyle.link, emoji="📖", url=res_source_url)
            audio_source_button = discord.ui.Button(label="Pronounciations", style=discord.ButtonStyle.link, emoji="🔈", url=res_phonetic_sound)
            view.add_item(url_source_button)
            if res_phonetic_sound is not None:
                view.add_item(audio_source_button)
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            await ctx.send(f"An error occured when sending embed: {e}", ephemeral=True)
        

        
