# cogs/trivia.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import json
from typing import Dict
import pathlib

TRIVIA_FILE = pathlib.Path(__file__).parent.parent / "genshin_trivia/jsons/genshin_trivia.json"

class TriviaView(discord.ui.View):
    def __init__(self, question_data: Dict, timeout_seconds: int = 15):
        super().__init__(timeout=timeout_seconds)
        self.question_data = question_data
        self.question = question_data["question"]
        self.options = question_data["options"]
        self.correct = question_data["correct"]
        self.difficulty = question_data["difficulty"]
        
        self.answered_users = set()
        self.timer_task = None
        self.seconds_left = timeout_seconds

        # Add dropdown immediately
        self.add_item(self.create_answer_select())

        # Add cancel button
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
        btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
        btn.callback = self.cancel_callback
        return btn

    async def select_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.answered_users:
            await interaction.response.send_message("You've already answered this trivia!", ephemeral=True)
            return

        self.answered_users.add(user_id)

        selected_index = int(interaction.data["values"][0])
        chosen_answer = self.options[selected_index]

        is_correct = chosen_answer == self.correct

        # User feedback
        feedback = "✅ **Correct!**" if is_correct else f"❌ **Wrong!**\nThe correct answer was: **{self.correct}**"
        await interaction.response.send_message(feedback, ephemeral=True)

        # Visual feedback
        embed = interaction.message.embeds[0]
        if is_correct:
            embed.color = discord.Color.green()
            embed.set_footer(text=f"Correct! Answered by {interaction.user.display_name}")
        else:
            embed.color = discord.Color.red()
            embed.set_footer(text=f"Wrong • Correct: {self.correct} • Answered by {interaction.user.display_name}")

        # Disable select menu
        self.children[0].disabled = True
        await interaction.message.edit(embed=embed, view=self)

        # Optional: stop timer on correct answer
        if is_correct and self.timer_task:
            self.timer_task.cancel()

    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="Trivia Cancelled",
            description=f"Cancelled by {interaction.user.mention}",
            color=discord.Color.greyple()
        )
        await interaction.message.edit(embed=embed, view=None)

    async def on_timeout(self):
        if any("Correct!" in e.footer.text for e in self.message.embeds or []):
            return  # someone already answered correctly

        embed = discord.Embed(
            title="⏰ Time's Up!",
            description=f"The correct answer was: **{self.correct}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="Question", value=self.question, inline=False)
        self.clear_items()
        try:
            await self.message.edit(embed=embed, view=self)
        except:
            pass

    async def countdown_timer(self, message: discord.Message):
        self.message = message  # store reference for on_timeout
        try:
            while self.seconds_left > 0:
                await asyncio.sleep(1)
                self.seconds_left -= 1

                if self.seconds_left % 2 == 0:  # update every 2 seconds
                    embed = discord.Embed(
                        title=f"Genshin Trivia • {self.difficulty.capitalize()}",
                        description=f"**{self.question}**\n\n⏳ **{self.seconds_left}s** remaining",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="One attempt per person • Multiple players can join!")
                    try:
                        await message.edit(embed=embed)
                    except discord.errors.NotFound:
                        return
        except asyncio.CancelledError:
            pass


class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.questions = []
        self.load_questions()

    def load_questions(self):
        try:
            with open(TRIVIA_FILE, "r", encoding="utf-8") as f:
                self.questions = json.load(f)
            print(f"Loaded {len(self.questions)} trivia questions")
        except Exception as e:
            print(f"Failed to load trivia: {e}")

    @app_commands.command(name="trivia", description="Start a Genshin Impact trivia question")
    async def trivia(self, interaction: discord.Interaction):
        if not self.questions:
            await interaction.response.send_message("No trivia questions loaded!", ephemeral=True)
            return

        question_data = random.choice(self.questions)
        
        view = TriviaView(question_data, timeout_seconds=15)
        
        embed = discord.Embed(
            title=f"Genshin Trivia • {question_data['difficulty'].capitalize()}",
            description=f"**{question_data['question']}**\n\n⏳ **15 seconds** to answer!",
            color=discord.Color.blue()
        )
        embed.set_footer(text="One attempt per person • Multiple players can join!")

        message = await interaction.response.send_message(embed=embed, view=view)
        
        # Start the countdown
        view.timer_task = asyncio.create_task(view.countdown_timer(await interaction.original_response()))


async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))