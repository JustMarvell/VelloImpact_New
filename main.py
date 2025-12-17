import settings
import discord
from discord import app_commands
from discord.ext import commands
import connections.firebase as fb

logger = settings.logging.getLogger("bot")
cogs_logger = settings.logging.getLogger("cogs")
tree_logger = settings.logging.getLogger("tree")

class Client(commands.Bot):
    async def setup_hook(self):
        logger.info(f'User : {self.user} (ID : {self.user.id})')
        
        # load cogs
        await load_cogs()
        
        # try :
        #     synced = await self.tree.sync()
        #     tree_logger.info(f"Synced {len(synced)} commands to global")
        # except Exception:
        #     pass
        tree_logger.info(msg="Bot is Ready!")
        
async def load_cogs():
    """Load all cogs"""
    tree_logger.info("Loading cogs...!")
    for cogs in settings.COGS_DIR.glob("*.py"):
        if cogs.name != "__init__.py":
            await client.load_extension(f'cogs.{cogs.name[:-3]}')
            # log the commands in the logger
            cogs_logger.info(f'Loaded ({cogs.name})')
        
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.presences = False
intents.guilds = True
intents.members = False
client = Client(command_prefix="!", intents=intents, help_command=None)

@client.tree.command(name = "reload_commands", description = "Reload all commands")
async def reload_commands(interaction: discord.Interaction):
    """Reload all commands"""
    try:
        reloaded_cogs = 0
        tree_logger.info("Reloading cogs...!")
        for cogs in settings.COGS_DIR.glob("*.py"):
            if cogs.name != "__init__.py":
                await client.reload_extension(f'cogs.{cogs.name[:-3]}')
                cogs_logger.info(f'Loaded ({cogs.name})')
                reloaded_cogs += 1
                
        # synced = await client.tree.sync()
        # tree_logger.info(f"Synced {len(synced)} commands to global")
        
        await interaction.response.send_message(f'Reloaded : {reloaded_cogs} cogs. Auto delete after 4 Seconds', delete_after=4, ephemeral=True)
    except Exception as e:
        tree_logger.error(f"Error reloading cogs: {e}")
        await interaction.response.send_message(f'Error reloading cogs: {e}', ephemeral=True)
        
@client.tree.command(name = "sync_commands", description = "Sync all commands")
async def sync_commands(interaction: discord.Interaction):
    """Sync all commands"""
    try:
        tree_logger.info("Syncing commands...!")
        synced = await client.tree.sync()
        tree_logger.info(f"Synced {len(synced)} commands to global")
        
        await interaction.response.send_message(f'Synced : {len(synced)} cogs. Auto delete after 4 Seconds', delete_after=4, ephemeral=True)
    except Exception as e:
        tree_logger.error(f"Error on Sync: {e}")
        await interaction.response.send_message(f'Error on Sync: {e}', ephemeral=True)
    
@client.event
async def on_ready():
    # set bot status
    await client.change_presence(activity=discord.Game(name="VelloImpact Bot is Online!"))

fb.initialize_app()
client.run(settings.DISCORD_API_SECRET, root_logger = True)