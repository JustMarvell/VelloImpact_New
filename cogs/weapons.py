from discord.ext import commands
from discord import app_commands
import controllers.weapons as wc
import discord
import typing
import connections.webhook as wb
import random

async def setup(bot : commands.Bot):
    await bot.add_cog(Weapons(bot)) 

class Weapons(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.hybrid_command()
    async def show_weapon_list(self, ctx : commands.Context):
        """ Return a list of available weapons """
        
        field1 = ""
        
        data = await wc.get_weapon_list()
        
        weapon_index = 1
        
        for weapon in data:
            field1 += f'{weapon_index}. {weapon}\n'
            weapon_index += 1
            
        data = {
            "embeds": [
                {
                    "title": "WEAPON LIST"
                },
                {
                    "description": field1
                }
            ],
                "username": "[/] BUFF_VelloImpact",
                "attachments": []
            }
        
        await ctx.send("Showing List....", delete_after=3)
        
        status = await wb.PostWebhook(data)
        if status != True:
            await ctx.send("Failed to Get the list. Please try again in a few moments.")
        
    async def weapon_autocomplete(
        self,
        ctx : commands.Context,
        current : str
    ) -> typing.List[app_commands.Choice[str]]:
        data = []
        weaponlist = await wc.get_weapon_list()
        weaponlist.append('random')
        for weapon in weaponlist:
            if current.lower() in weapon.lower():
                data.append(app_commands.Choice(name = weapon, value = weapon))
        return data[:25]
    
    @commands.hybrid_command()
    @app_commands.autocomplete(weapon_name = weapon_autocomplete)
    async def show_weapon(self, ctx : commands.Context, *, weapon_name : str):
        """ Return a description of the selected weapon or [random] """
        
        if weapon_name == 'random':
            lst = await wc.get_weapon_list()
            c = len(lst) - 1
            r = random.randint(0, c)
            weapon = lst[r]
        else:
            weapon = weapon_name
        
        if weapon != None:
            embed = discord.Embed(title = f'Genshin Impact Fandom Wiki | Weapons | {weapon_name}')
        else:
            await ctx.send(f'There is no weapon named {weapon_name} in the database')
            return
        
        data = await wc.get_weapon_data(weapon)
        if data == 1:
            await ctx.send(f'No data found for {weapon}')
            return
        elif data == 2:
            await ctx.send(f'Error reading data for {weapon}')
            return
        
        id = data.get('id')
        weapon_type = data.get('weapon_type')
        quality = data.get('weapon_quality')
        stars = await wc.convert_quality_to_star(quality)
        base_attack = data.get('base_attack')
        # secondary_attribute_type = data.get('secondary_attribute_type')
        secondary_attribute = data.get('secondary_attribute')
        weapon_description = data.get('weapon_description')
        weapon_skill_name = data.get('weapon_skill_name')
        weapon_skill_description = data.get('weapon_skill_description')
        weapon_icon = data.get('weapon_icon')
        embed_color = await wc.get_color_based_on_quality(quality)
        
        # weapon_type = await wc.get_weapon_type(id)
        # quality = await wc.get_weapon_quality(id)
        # stars = await wc.convert_quality_to_star(quality)
        # base_attack = await wc.get_weapon_base_attack(id)
        # secondary_attribute_type = await wc.get_secondary_attribute_type(id)
        # secondary_attribute = await wc.get_secondary_attribute(id)
        # weapon_description = await wc.get_weapon_description(id)
        # weapon_skill_name = await wc.get_weapon_skill_name(id)
        # weapon_skill_description = await wc.get_weapon_skill_description(id)
        # weapon_icon = await wc.get_weapon_icon(id)
        # embed_color = await wc.get_color_based_on_quality(id)
        
        weapon_info_field = f'Name : {weapon}\nWeapon Type : {weapon_type}\nWeapon Quality : {stars}'
        weapon_base_stats_field = f'Base ATK : {base_attack}\nSecondary Attribute : {secondary_attribute}'
        weapon_skill_field = f'{weapon_skill_description}'
        
        embed.description = weapon_description
        embed.color = embed_color
        embed.add_field(name = "WEAPON INFO", value = weapon_info_field, inline = False)
        embed.add_field(name = "WEAPON STATS", value = weapon_base_stats_field, inline = False)
        embed.add_field(name = f'PASSIVE SKILL : {weapon_skill_name}', value = weapon_skill_field, inline = False)
        embed.set_image(url = weapon_icon)
        embed.set_footer(text = "Data collected from Genshin Impact Fandom Wiki", icon_url = "https://static.wikia.nocookie.net/6a181c72-e8bf-419b-b4db-18fd56a0eb60")
        
        await ctx.send(embed = embed)