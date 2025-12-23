# cogs/trivia.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import json
from typing import List, Dict
import pathlib

# Assume you have your trivia questions in a json file
TRIVIA_FILE = pathlib.Path(__file__).parent.parent / "genshin_trivia/jsons/genshin_trivia.json"


class TriviaView(discord.ui.View):
    def __init__(self, question_data: Dict, timeout_seconds: int = 10):
        super().__init__(timeout=timeout_seconds)
        self.question_data = question_data
        self.question = question_data["question"]
        self.options = question_data["options"]
        self.correct = question_data["correct"]
        self.difficulty = question_data["difficulty"]
        
        self.answered_users = set()  # users who already answered this instance
        self.timer_task = None
        self.original_message = None
        self.seconds_left = timeout_seconds
        self.timer_running = False

    @discord.ui.button(label="Show Options", style=discord.ButtonStyle.primary)
    async def show_options(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Prevent multiple people from revealing at once (optional)
        if self.timer_running:
            await interaction.response.send_message("Options already revealed!", ephemeral=True)
            return

        self.timer_running = True
        self.clear_items()  # remove "Show Options"

        # Add answer buttons
        for i, option in enumerate(self.options):
            btn = discord.ui.Button(
                label=f"{chr(65+i)}. {option[:40]}...",  # truncate long answers
                style=discord.ButtonStyle.secondary,
                custom_id=f"ans_{i}"
            )
            btn.callback = self.answer_callback
            self.add_item(btn)

        # Add cancel button
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

        embed = self.create_embed()
        embed.description = f"{self.question}\n\n**Choose your answer!**\nTime remaining: **{self.seconds_left}s**"

        await interaction.response.edit_message(embed=embed, view=self)
        
        # Start the countdown
        self.timer_task = asyncio.create_task(self.countdown_timer(interaction.message))

    async def answer_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.answered_users:
            await interaction.response.send_message("You've already answered this trivia!", ephemeral=True)
            return

        self.answered_users.add(user_id)

        # Find which answer was chosen
        answer_index = int(interaction.data["custom_id"].split("_")[1])
        chosen_answer = self.options[answer_index]

        is_correct = chosen_answer == self.correct

        # Feedback to user
        feedback = "✅ **Correct!**" if is_correct else f"❌ **Wrong!**\nThe correct answer was: **{self.correct}**"
        await interaction.response.send_message(feedback, ephemeral=True)

        # Visual feedback on main message
        for i, child in enumerate(self.children):
            if i >= len(self.options):  # skip cancel button
                continue
            if i == answer_index:
                child.style = discord.ButtonStyle.success if is_correct else discord.ButtonStyle.danger
            if self.options[i] == self.correct:
                child.style = discord.ButtonStyle.success

        # Disable all answer buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label.startswith(("A.", "B.", "C.", "D.")):
                child.disabled = True

        await interaction.message.edit(view=self)

        # Stop timer if someone answered correctly
        if is_correct:
            if self.timer_task:
                self.timer_task.cancel()

    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="Trivia Cancelled",
            description=f"Question cancelled by {interaction.user.mention}",
            color=discord.Color.greyple()
        )
        await interaction.message.edit(embed=embed, view=None)

    async def countdown_timer(self, message: discord.Message):
        self.original_message = message
        try:
            while self.seconds_left > 0:
                await asyncio.sleep(1)
                self.seconds_left -= 1

                if self.seconds_left % 2 == 0:  # update every 2 seconds to reduce rate limits
                    embed = self.create_embed()
                    embed.description = f"{self.question}\n\n**Time remaining: {self.seconds_left}s**"
                    try:
                        await message.edit(embed=embed)
                    except discord.errors.NotFound:
                        return  # message deleted
        except asyncio.CancelledError:
            pass
        finally:
            # Time's up or cancelled
            if self.seconds_left <= 0 and not any(c.style == discord.ButtonStyle.success for c in self.children):
                embed = discord.Embed(
                    title="⏰ Time's Up!",
                    description=f"The correct answer was: **{self.correct}**",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Question", value=self.question, inline=False)
                try:
                    await message.edit(embed=embed, view=None)
                except:
                    pass

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"Genshin Trivia  •  {self.difficulty.capitalize()}",
            description=self.question,
            color=discord.Color.blue()
        )
        embed.set_footer(text="You have one attempt • Multiple players can join!")
        return embed


class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.questions: List[Dict] = []
        self.load_questions()

    def load_questions(self):
        try:
            with open(TRIVIA_FILE, "r", encoding="utf-8") as f:
                self.questions = json.load(f)
            print(f"Loaded {len(self.questions)} trivia questions")
        except FileNotFoundError:
            print(f"Trivia file not found: {TRIVIA_FILE}")
            self.questions = []
        except Exception as e:
            print(f"Error loading trivia: {e}")

    @app_commands.command(name="trivia", description="Start a Genshin Impact trivia question")
    async def trivia(self, interaction: discord.Interaction):
        if not self.questions:
            await interaction.response.send_message("No trivia questions available!", ephemeral=True)
            return

        question_data = random.choice(self.questions)
        
        view = TriviaView(question_data, timeout_seconds=10)
        embed = view.create_embed()
        embed.description = f"{question_data['question']}\n\n⏳ **10 seconds** to answer!"

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))