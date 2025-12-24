from discord.ext import commands
from discord import app_commands
import controllers.randoms as rc
import discord
import requests
import random

roasts = {
    '0-9' : {
        'roasts' : ['"bro is literally on toddler negative aura"', '"skill issue + bottle dependency"', '"ratio\'d by nap time"'],
        'img' : ['https://i.pinimg.com/736x/73/24/e1/7324e1fe9919215d264f12e4753a549b.jpg', 'https://i.pinimg.com/736x/1c/97/a4/1c97a450c8b2bca9b10b80c92d1bfef3.jpg', 'https://i.pinimg.com/736x/e5/a1/c0/e5a1c0a655bf08bedb23e96010ef7e67.jpg']
    },
    '10-17' : {
        'roasts' : ['"you peaked in roblox 2020 and never recovered"', '"your aura is 2019 TikTok dance energy"', '"homework merchant 😭"', '"talks like they discovered sarcasm yesterday"'],
        'img' : ['https://i.pinimg.com/736x/aa/5a/e0/aa5ae0092a9818d3b616caca940a19ed.jpg', 'https://i.pinimg.com/736x/e6/d1/2a/e6d12adc8c5b7f46f636d2a9a9e53378.jpg', 'https://i.pinimg.com/736x/14/ca/2a/14ca2aac31f3ec59ceef221a159251de.jpg']
    },
    '18-25' : {
        'roasts' : ['"your entire personality is a Pinterest board from 2021"', '"broke philosophy major energy"', '"still romanticizing 3am waffle house"', '"job application speedrun any%"', '"crypto bagholder survivor"'],
        'img' : ['https://i.pinimg.com/736x/03/74/41/0374414cbd9ae9d706ea7a0c93b2ee79.jpg', 'https://i.pinimg.com/736x/48/2d/21/482d21bb0771bc92d5fa3ebfdda9114e.jpg', 'https://i.pinimg.com/736x/f2/d3/7a/f2d37ab310e7fa353dda476cff35a3f3.jpg']
    },
    '26-39' : {
        'roasts' : ['"you\'re basically just adult Pokémon now… still collecting debt"', '"your vibe is \'I have a 401k and trauma\'"', '"mid-life crisis loading… (0%)"', '"unironically says \'back in my day\' about 2017"', '"group chat owner, life avoider"'],
        'img' : ['https://i.pinimg.com/736x/5a/01/f1/5a01f1b639b02860f35a2a4b399a7e4d.jpg', 'https://i.pinimg.com/736x/45/8e/7b/458e7b3b0ea86fc89a1673226a9c42e2.jpg', 'https://i.pinimg.com/736x/c1/bf/32/c1bf3232084ac94a0f776323af2023be.jpg']
    },
    '40-60' : {
        'roasts' : ['"Facebook comment section final boss"', '"your humor got stuck in 2009 chain email"', '"\'I\'m not old I\' vintage\' cope"', '"still fighting the war against autocorrect"', '"dad joke dps merchant"'],
        'img' : ['https://i.pinimg.com/736x/65/b9/c9/65b9c99b7e8ed3662a4bdf8f25789096.jpg', 'https://i.pinimg.com/736x/38/8e/fc/388efcee47d59cafe1d92cbf4bab022f.jpg', 'https://i.pinimg.com/736x/0c/bf/89/0cbf89438d9280747d31cc71e2b7f7c8.jpg']
    },
    '61-75' : {
        'roasts' : ['"you\'re on legendary difficulty life mode"', '"boomer but make it slay"', '"your clapback latency is 3 business days"', '"still calls group texts \'the group message\'"', '"retired but still ratio-ing politicians on Facebook"'],
        'img' : ['https://i.pinimg.com/736x/65/b9/c9/65b9c99b7e8ed3662a4bdf8f25789096.jpg', 'https://i.pinimg.com/736x/f7/5d/76/f75d76626d0e20b5d5ae4342baed0deb.jpg', 'https://i.pinimg.com/736x/8f/61/97/8f61979e578e3b4a1ec76804df206868.jpg']
    },
    '76-100' : {
        'roasts' : ['"you\'ve been on this server longer than the server has existed"', '"OG of the planet fr"', '"your lore is multiple DLCs deep"', '"you\'ve seen more plot twists than the Bible"', '"respectfully… you\'re built different (and ancient)"', '"final form unlocked, no continues left"'],
        'img' : ['https://i.pinimg.com/736x/65/b9/c9/65b9c99b7e8ed3662a4bdf8f25789096.jpg', 'https://i.pinimg.com/736x/8a/a8/fa/8aa8faa0054b45fd580383e46ff0823d.jpg', 'https://i.pinimg.com/736x/23/e5/15/23e515519a1f2787573bf3677aa35d35.jpg']
    }
}

gender_data = {
    'male' : {
        'color' : 162022,
        'img' : 'https://i.pinimg.com/736x/b6/d0/4a/b6d04af994a3e975b3b6c05783d44c14.jpg'
    },
    'female' : {
        'color' : 14821763,
        'img' : 'https://i.pinimg.com/1200x/b6/46/af/b646af421324ccb832445a908de41da8.jpg'
    }
}

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

    @commands.hybrid_command()
    async def guess_age(self, ctx: commands.Context, *, name: str | None):
        """ Guess the age from the given name 
        Args:
            name: The name you want to guess the age
        """
        try:
            await ctx.defer()
        except Exception:
            pass
        
        if not name or name is None:
            await ctx.send(f"Please provide a valid name!", ephemeral=True)
            return
        
        BASE_URL = 'https://api.agify.io'
        
        try:
            response = requests.get(f"{BASE_URL}?name={name}")
            
            if response.status_code != 200:
                await ctx.send(f"Something wrong when fetching the response! Return code : {response.status_code}")
                return
        except Exception as e:
            await ctx.send(f"An error occured when getting response : {e}", ephemeral=True)
            return
        
        age = response.json().get('age')
        
        if age is None:
            await ctx.send(f"{name} is not a valid name, please try again with a different name!")
            return
        
        if age >= 76:
            roast = random.choice(roasts.get('76-100').get('roasts'))
            img = random.choice(roasts.get('76-100').get('img'))
        elif age >= 61:
            roast = random.choice(roasts.get('61-75').get('roasts'))
            img = random.choice(roasts.get('61-75').get('img'))
        elif age >= 40:
            roast = random.choice(roasts.get('40-60').get('roasts'))
            img = random.choice(roasts.get('40-60').get('img'))
        elif age >= 26:
            roast = random.choice(roasts.get('26-39').get('roasts'))
            img = random.choice(roasts.get('26-39').get('img'))
        elif age >= 18:
            roast = random.choice(roasts.get('18-25').get('roasts'))
            img = random.choice(roasts.get('18-25').get('img'))
        elif age >= 10:
            roast = random.choice(roasts.get('10-17').get('roasts'))
            img = random.choice(roasts.get('10-17').get('img'))
        else:
            roast = random.choice(roasts.get('0-9').get('roasts'))
            img = random.choice(roasts.get('0-9').get('img'))

        try:
            embed = discord.Embed(
                color=1828597,
                title="Based on your name, Here's my prediction!"
            )
            embed.set_image(url=img)
            embed.add_field(
                name="Name :",
                value=f"{name}",
                inline=False,
            )
            embed.add_field(
                name="Age :",
                value=f"{age}",
                inline=False,
            )
            embed.add_field(
                name="  ",
                value=roast,
                inline=False,
            )
            embed.set_footer(
                text="Age prediction by agify.io",
            )
            
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Failed when trying to sed embed message : {e}", ephemeral=True)
            
    @commands.hybrid_command()
    async def guess_gender(self, ctx: commands.Context, *, name: str | None):
        """ Guess the gender of the specified name 
        Args:
            name : The name that want to be guessed
        """
        try:
            await ctx.defer()
        except Exception:
            pass
        
        if not name or name is None:
            await ctx.send(f"Please provide a valid name!", ephemeral=True)
            return
        
        BASE_URL = 'https://api.genderize.io'
        
        try:
            response = requests.get(f"{BASE_URL}?name={name}")
            
            if response.status_code != 200:
                await ctx.send(f"Something wrong when fetching the response! Return code : {response.status_code}")
                return
        except Exception as e:
            await ctx.send(f"An error occured when getting response : {e}", ephemeral=True)
            return
        
        gender = response.json().get('gender')
        probability = response.json().get('probability')
        
        if gender is None:
            await ctx.send(f"{name} is not a valid name, please try again with a different name!")
            return
        elif gender == 'male':
            img = gender_data.get('male').get('img')
            color = gender_data.get('male').get('color')
        elif gender == 'female':
            img = gender_data.get('female').get('img')
            color = gender_data.get('female').get('color')
        
        try:
            embed = discord.Embed(
                color=color,
                title="Based on your name, Here's my prediction!"
            )
            embed.set_image(url=img)
            embed.add_field(
                name="Name :",
                value=f"{name}",
                inline=False,
            )
            embed.add_field(
                name="Gender :",
                value=f"{gender.capitalize()}",
                inline=False,
            )
            embed.add_field(
                name="Probability : ",
                value=f"{probability * 100}%",
                inline=False,
            )
            embed.set_footer(
                text="Gender prediction by genderize.io",
            )
            
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Failed when trying to sed embed message : {e}", ephemeral=True)
            
    @commands.hybrid_command()
    async def get_random_dog_image(self, ctx: commands.Context):
        """ Get a random dog image """
        try:
            await ctx.defer()
        except Exception():
            pass
        
        BASE_URL = 'https://dog.ceo/api/breeds/image/random'

        try:
            response = requests.get(f"{BASE_URL}")
            
            if response.status_code != 200:
                await ctx.send(f"Something wrong when fetching the response! Return code : {response.status_code}")
                return
            
            status = response.json().get('status')
            img = response.json().get('message')
            
            if status != 'success':
                await ctx.send(f"Something wrong when fetching the response! Status : {status}")
                return
        except Exception as e:
            await ctx.send(f"An error occured when getting response : {e}", ephemeral=True)
            return
        
        try:
            embed = discord.Embed(
                color=1349855,
                title="Here's an image of a dog!",
            )
            embed.set_image(url=img)
            embed.set_footer(
                text="Image provided by dog.ceo",
                icon_url="https://dog.ceo/img/dog-api-logo.svg",
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"Failed when trying to sed embed message : {e}", ephemeral=True)
        