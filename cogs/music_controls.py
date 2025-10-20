import discord
from discord.ext import commands
from discord import app_commands
from youtubesearchpython import VideosSearch
import yt_dlp

class MusicControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Presistent view
        
    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing():
            voice_client.pause()
            # Update button states
            self.pause_button.disabled = True
            self.resume_button.disabled = False
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("Paused", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing", ephemeral=True)

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.primary, disabled=True)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_paused():
            voice_client.resume()
            # update button states
            self.pause_button.disabled = False
            self.resume_button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("Resumed", ephemeral=True)
        else:
            await interaction.response.send_message("Not paused", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()  # Triggers play_next via after_playing
            await interaction.response.send_message("Skipped current song", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing to skip!", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global queue
        if not interaction.guild.voice_client:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)
            return
        
        voice_client = interaction.guild.voice_client
        queue.clear()
        voice_client.stop()
        # Disable all buttons except Stop
        self.pause_button.disabled = True
        self.resume_button.disabled = True
        self.skip_button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send("Stopped", ephemeral=True)