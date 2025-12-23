# cogs/trivia.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import json
from typing import Dict, Optional
import pathlib

TRIVIA_FILE = pathlib.Path(__file__).parent.parent / "genshin_trivia/jsons/genshin_trivia.json"

class GameState:
    ACTIVE = "active"
    ENDED = "ended" 
    CANCELLED = "cancelled"

class TriviaView(discord.ui.View):
    def __init__(self, question_data: Dict, timeout_seconds: int = 20):
        super().__init__(timeout=timeout_seconds)
        self.question_data = question_data
        self.question = question_data["question"]
        self.options = question_data["options"]
        self.correct = question_data["correct"]
        self.difficulty = question_data["difficulty"]
        self.image_url = question_data.get("image", None)
        
        self.answered_users = set()
        self.correct_users = set()  # Changed from list to set
        self.game_state = GameState.ACTIVE
        self.timer_task = None
        self.seconds_left = timeout_seconds
        self.message_ref = None
        self.latest_user = None

        # Add UI components
        self.add_item(self.create_answer_select())
        self.add_item(self.create_cancel_button())

    def create_answer_select(self):
        select = discord.ui.Select(
            placeholder="Select your answer...",
            options=[
                discord.SelectOption(label=f"{chr(65+i)}. {opt}", value=str(i))
                for i, opt in enumerate(self.options)
            ],
            min_values=1,
            max_values=1,
            custom_id="trivia_answer"
        )
        select.callback = self.select_callback
        return select

    def create_cancel_button(self):
        btn = discord.ui.Button(
            label="Cancel", 
            style=discord.ButtonStyle.red,
            custom_id="trivia_cancel"
        )
        btn.callback = self.cancel_callback
        return btn

    def disable_all_components(self):
        """Disable all interactive components"""
        for child in self.children:
            child.disabled = True

    async def end_game(self, embed: discord.Embed, disable_ui: bool = True):
        """End the game and update UI"""
        if self.game_state != GameState.ACTIVE:
            return  # Already ended
        
        self.game_state = GameState.ENDED
        
        # Cancel timer task
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        
        # Disable UI if requested
        if disable_ui:
            self.disable_all_components()
        
        # Update message
        if self.message_ref:
            try:
                await self.message_ref.edit(embed=embed, view=self if disable_ui else None)
            except discord.errors.NotFound:
                pass  # Message already deleted

    async def select_callback(self, interaction: discord.Interaction):
        # Check if game is still active
        if self.game_state != GameState.ACTIVE:
            await interaction.response.send_message("This trivia game has already ended!", ephemeral=True)
            return

        user_id = interaction.user.id
        if user_id in self.answered_users:
            await interaction.response.send_message("You've already answered this trivia!", ephemeral=True)
            return

        self.answered_users.add(user_id)
        self.latest_user = interaction.user.mention

        try:
            selected_index = int(interaction.data["values"][0])
            chosen_answer = self.options[selected_index]
        except (KeyError, IndexError, ValueError):
            await interaction.response.send_message("Invalid selection. Please try again.", ephemeral=True)
            return

        is_correct = chosen_answer == self.correct
        if is_correct:
            self.correct_users.add(self.latest_user)

        # User feedback - always send privately
        feedback = "✅ **Correct!**" if is_correct else f"❌ **Wrong!**"
        await interaction.response.send_message(feedback, ephemeral=True)

        # Update embed to show player's answer and keep game going
        await self.update_embed_with_answer(interaction, chosen_answer, is_correct)

    async def update_embed_with_answer(self, interaction: discord.Interaction, chosen_answer: str, is_correct: bool):
        """Update the embed to show the latest answer and continue the game"""
        try:
            # Get current embed
            embed = self.create_embed()
            
            # Add summary of all answers so far
            if len(self.answered_users) > 0:
                users = ""
                for i in len(self.correct_users):
                    users += f"{i}\n"
                
                embed.add_field(
                    name="📊 Correct Users", 
                    value=users, 
                    inline=True
                )
            
            # Keep the same image
            if self.image_url:
                embed.set_thumbnail(url=self.image_url)
            
            # Update the message
            await interaction.message.edit(embed=embed, view=self)
            
        except Exception as e:
            print(f"Error updating embed: {e}")

    async def cancel_callback(self, interaction: discord.Interaction):
        if self.game_state != GameState.ACTIVE:
            await interaction.response.send_message("This trivia game has already ended!", ephemeral=True)
            return

        embed = discord.Embed(
            title="❌ Trivia Cancelled",
            description=f"Cancelled by {interaction.user.mention}",
            color=discord.Color.greyple()
        )
        embed.add_field(name="Question", value=self.question, inline=False)
        embed.add_field(name="Correct Answer", value=self.correct, inline=False)
        embed.add_field(name="Total Participants", value=str(len(self.answered_users)), inline=True)
        
        if self.image_url:
            embed.set_thumbnail(url=self.image_url)

        await interaction.response.defer()
        await self.end_game(embed, disable_ui=False)

    async def on_timeout(self):
        # Only handle timeout if game is still active
        if self.game_state != GameState.ACTIVE:
            return

        # Count correct and incorrect answers
        correct_count = 0
        total_answers = len(self.answered_users)
        
        # For timeout, we don't have individual answers tracked, so just show the stats
        embed = discord.Embed(
            title="⏰ Time's Up!",
            description=f"**{self.question}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="Correct Answer", value=f"**{self.correct}**", inline=False)
        embed.add_field(name="Total Participants", value=str(total_answers), inline=True)
        embed.add_field(name="Time Limit", value="20 seconds", inline=True)
        embed.set_footer(text="⏰ Time expired")
        
        if self.image_url:
            embed.set_thumbnail(url=self.image_url)

        await self.end_game(embed, disable_ui=True)

    async def countdown_timer(self, message: discord.Message):
        """Optimized countdown timer that updates every 3 seconds"""
        self.message_ref = message
        try:
            while self.seconds_left > 0 and self.game_state == GameState.ACTIVE:
                await asyncio.sleep(3)  # Update every 3 seconds instead of 2
                self.seconds_left -= 3
                
                if self.seconds_left < 0:
                    self.seconds_left = 0
                
                # Only update if game is still active
                if self.game_state == GameState.ACTIVE:
                    embed = self.create_embed()
                    
                    # Add summary of all answers so far
                    if len(self.answered_users) > 0:
                        users = ""
                        for i in len(self.correct_users):
                            users += f"{i}\n"
                        
                        embed.add_field(
                            name="📊 Correct Users", 
                            value=users, 
                            inline=True
                        )
                    
                    try:
                        await message.edit(embed=embed)
                    except discord.errors.NotFound:
                        return  # Message was deleted
                    except discord.errors.Forbidden:
                        return  # No permission to edit
                        
        except asyncio.CancelledError:
            pass  # Timer was cancelled, which is expected
        except Exception as e:
            print(f"Timer error: {e}")
        
    def create_embed(self) -> discord.Embed:
        """Create the main trivia embed"""
        embed = discord.Embed(
            title=f"🎮 Genshin Trivia • {self.difficulty.capitalize()}",
            description=f"**{self.question}**",
            color=discord.Color.blue()
        )
        
        # Add timer field
        timer_emoji = "🔴" if self.seconds_left <= 5 else "🟡" if self.seconds_left <= 10 else "🟢"
        embed.add_field(
            name=f"{timer_emoji} Time Remaining", 
            value=f"**{self.seconds_left}s**", 
            inline=True
        )
        
        embed.add_field(
            name="👥 Players", 
            value=str(len(self.answered_users)), 
            inline=True
        )
        
        embed.set_footer(
            text="Select an answer • Cancel to end early • Multiple players can join!",
            icon_url="https://i.imgur.com/AfFp7Hd.png"
        )

        # Use thumbnail instead of image for faster loading
        if self.image_url:
            embed.set_thumbnail(url=self.image_url)

        return embed

class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.questions = []
        self.active_games = set()  # Track active games to prevent conflicts
        self.load_questions()

    def load_questions(self):
        """Load trivia questions from JSON file"""
        try:
            with open(TRIVIA_FILE, "r", encoding="utf-8") as f:
                self.questions = json.load(f)
            print(f"✅ Loaded {len(self.questions)} trivia questions")
        except Exception as e:
            print(f"❌ Failed to load trivia: {e}")
            self.questions = []

    @app_commands.command(name="trivia", description="Start a Genshin Impact trivia question")
    async def trivia(self, interaction: discord.Interaction):
        if not self.questions:
            await interaction.response.send_message("❌ No trivia questions available!", ephemeral=True)
            return

        # Check if there's already an active trivia in this channel
        channel_id = interaction.channel.id
        if channel_id in self.active_games:
            await interaction.response.send_message(
                "⚠️ There's already an active trivia game in this channel!", 
                ephemeral=True
            )
            return

        question_data = random.choice(self.questions)
        
        try:
            # Create view and embed
            view = TriviaView(question_data, timeout_seconds=20)
            embed = view.create_embed()
            
            # Add initial timer field
            embed.add_field(name="⏱️ Time", value="**20s**", inline=True)
            
            # Send message
            await interaction.response.send_message(embed=embed, view=view)
            message = await interaction.original_response()
            
            # Register this game as active
            self.active_games.add(channel_id)
            view.timer_task = asyncio.create_task(view.countdown_timer(message))
            
            # Clean up when game ends
            async def cleanup():
                await asyncio.sleep(1)  # Small delay to ensure cleanup
                self.active_games.discard(channel_id)
            
            # Schedule cleanup (this will run when the view is finished)
            asyncio.create_task(cleanup())
            
        except Exception as e:
            print(f"Error starting trivia: {e}")
            await interaction.response.send_message(
                "❌ Failed to start trivia game. Please try again.", 
                ephemeral=True
            )

    async def cog_unload(self):
        """Clean up when cog is unloaded"""
        # Cancel all active timer tasks
        for view in list(self.active_games):
            if view.timer_task and not view.timer_task.done():
                view.timer_task.cancel()
        self.active_games.clear()

async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))

