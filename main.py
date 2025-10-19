import settings
import discord
from discord import app_commands
from discord.ext import commands

logger = settings.logging.getLogger("bot")
cogs_logger = settings.logging.getLogger("cogs")
tree_logger = settings.logging.getLogger("tree")

class Client(commands.Bot):
    async def setup_hook(self):
        logger.info(f'User : {self.user} (ID : {self.user.id})')
        
        # load cogs
        await load_cogs()
        
        synced = await self.tree.sync()
        tree_logger.info(f"Synced {len(synced)} commands to global")
        
async def load_cogs():
    """Load all cogs"""
    for cogs in settings.COGS_DIR.glob("*.py"):
        if cogs.name != "__init__.py":
            await client.load_extension(f'cogs.{cogs.name[:-3]}')
            # log the commands in the logger
            cogs_logger.info(f'Loaded ({cogs.name})')
        
intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix="!", intents=intents, help_command=None)

@client.tree.command(name = "reload_commands", description = "Reload all commands")
async def reload_commands(interaction: discord.Interaction):
    """Reload all commands"""
    reloaded_cogs = 0
    for cogs in settings.COGS_DIR.glob("*.py"):
        if cogs.name != "__init__.py":
            await client.reload_extension(f'cogs.{cogs.name[:-3]}')
            reloaded_cogs += 1
    await interaction.response.send_message(f'Reloaded : {reloaded_cogs} cogs. Auto delete after 4 Seconds', delete_after=4)

client.run(settings.DISCORD_API_SECRET, root_logger = True)