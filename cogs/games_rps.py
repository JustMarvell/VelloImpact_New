# cogs/games_rps.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from typing import Dict
import uuid

class Moves:
    """Move enum with numeric values for calculation"""
    ROCK = "rock"           # 0
    PAPER = "paper"         # 1
    SCISOR = "scisor"       # 2
    
    # Mapping for number-based calculation
    _values = {
        ROCK: 0,
        PAPER: 1,
        SCISOR: 2
    }

def get_result(playerMove: Moves, botMoves: Moves) -> bool | None:
    """
    Determine the game result using number-based calculation.
    
    Logic: Rock=0, Paper=1, Scissor=2
    - If player == bot: DRAW (None)
    - If (player - bot + 3) % 3 == 1: WIN (True)
    - Otherwise: LOSE (False)
    
    Returns:
        True if Win, False if Lose, None if Draw
    """
    player_val = Moves._values.get(playerMove, 0)
    bot_val = Moves._values.get(botMoves, 0)
    
    if player_val == bot_val:
        return None  # Draw
    
    # If (player - bot) % 3 == 1, player wins
    return (player_val - bot_val) % 3 == 1

class GameState:
    ACTIVE = "active"
    ENDED = "ended" 
    CANCELLED = "cancelled"

class RpsView(discord.ui.View):
    def __init__(self, timeout_seconds: int = 60):
        super().__init__(timeout=timeout_seconds)
        
        # Game state
        self.game_id = str(uuid.uuid4())[:8]
        self.game_state = GameState.ACTIVE
        self.timer_task = None
        self.seconds_left = timeout_seconds
        self.message_ref = None
        
        # Track players - each user can only play once
        self.players: Dict[str, Dict] = {}  # user_id -> {"move": Moves, "bot_move": Moves, "result": str, "username": str}
        
        # Add UI components - Rock, Paper, Scissor buttons
        self.add_item(self.create_rock_button())
        self.add_item(self.create_paper_button())
        self.add_item(self.create_scissor_button())
        self.add_item(self.create_cancel_button())
    
    def create_rock_button(self):
        btn = discord.ui.Button(
            label = "Rock",
            style=discord.ButtonStyle.secondary,
            custom_id="rock_btn"
        )
        btn.callback = self.rock_btn_callback
        return btn
        
    def create_paper_button(self):
        btn = discord.ui.Button(
            label="Paper",
            style=discord.ButtonStyle.secondary,
            custom_id="paper_btn"
        )
        btn.callback = self.paper_btn_callback
        return btn
    
    def create_scissor_button(self):
        btn = discord.ui.Button(
            label="Scissor",
            style=discord.ButtonStyle.secondary,
            custom_id="scissor_btn"
        )
        btn.callback = self.scissor_btn_callback
        return btn

    def create_cancel_button(self):
        btn = discord.ui.Button(
            label="Cancel", 
            style=discord.ButtonStyle.red,
            custom_id="Rps_cancel"
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
            
    async def rock_btn_callback(self, interaction: discord.Interaction):
        """Handle Rock button press"""
        await self.play_move(interaction, Moves.ROCK)
    
    async def paper_btn_callback(self, interaction: discord.Interaction):
        """Handle Paper button press"""
        await self.play_move(interaction, Moves.PAPER)
    
    async def scissor_btn_callback(self, interaction: discord.Interaction):
        """Handle Scissor button press"""
        await self.play_move(interaction, Moves.SCISOR)
    
    async def play_move(self, interaction: discord.Interaction, player_move: Moves):
        """Process a player's move and determine the result"""
        if self.game_state != GameState.ACTIVE:
            await interaction.response.send_message("This game has already ended!", ephemeral=True)
            return
        
        user_id = str(interaction.user.id)
        
        # Check if user already played
        if user_id in self.players:
            await interaction.response.send_message("You've already made your move! Wait for the game to end.", ephemeral=True)
            return
        
        # Bot makes a random move
        bot_move = random.choice([Moves.ROCK, Moves.PAPER, Moves.SCISOR])
        
        # Determine result
        result = get_result(player_move, bot_move)
        
        if result is True:
            result_text = "🎉 **WIN**"
            result_emoji = "✅"
        elif result is False:
            result_text = "💔 **LOSE**"
            result_emoji = "❌"
        else:
            result_text = "🤝 **DRAW**"
            result_emoji = "⚪"
        
        # Store player's move and result
        self.players[user_id] = {
            "move": player_move.value,
            "bot_move": bot_move.value,
            "result": result_text,
            "username": interaction.user.name
        }
        
        # Create result embed
        player_move_emoji = self.get_move_emoji(player_move)
        bot_move_emoji = self.get_move_emoji(bot_move)
        
        embed = discord.Embed(
            title=f"🎮 Rock Paper Scissors - Game #{self.game_id}",
            description=f"**Results for {interaction.user.mention}**",
            color=discord.Color.blue() if result else discord.Color.red() if not result else discord.Color.greyple()
        )
        
        embed.add_field(
            name=f"{interaction.user.name}'s Move",
            value=f"{player_move_emoji} **{player_move.value.upper()}**",
            inline=True
        )
        
        embed.add_field(
            name="Bot's Move",
            value=f"{bot_move_emoji} **{bot_move.value.upper()}**",
            inline=True
        )
        
        embed.add_field(
            name="Result",
            value=f"{result_emoji} {result_text}",
            inline=False
        )
        
        embed.set_footer(text=f"Players participated: {len(self.players)}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def get_move_emoji(self, move: Moves) -> str:
        """Get emoji for a move"""
        emojis = {
            Moves.ROCK: "🪨",
            Moves.PAPER: "📄",
            Moves.SCISOR: "✂️"
        }
        return emojis.get(move, "❓")

    async def cancel_callback(self, interaction: discord.Interaction):
        """Handle cancel button press"""
        if self.game_state != GameState.ACTIVE:
            await interaction.response.send_message("This game has already ended!", ephemeral=True)
            return

        embed = discord.Embed(
            title="❌ Game Cancelled",
            description=f"Cancelled by {interaction.user.mention}",
            color=discord.Color.greyple()
        )
        
        if len(self.players) > 0:
            # Show all players and their results
            players_text = ""
            for player_id, player_data in self.players.items():
                players_text += f"{player_data['result']} - {player_data['username']} ({player_data['move']} vs {player_data['bot_move']})\n"
            embed.add_field(name="🏆 Players Results", value=players_text, inline=False)
        else:
            embed.add_field(name="Note", value="No players participated", inline=False)
        
        embed.add_field(name="Total Participants", value=str(len(self.players)), inline=True)

        await interaction.response.defer()
        await self.end_game(embed, disable_ui=False)

    async def on_timeout(self):
        """Handle view timeout"""
        # Only handle timeout if game is still active
        if self.game_state != GameState.ACTIVE:
            return
        
        # Create timeout embed with player results
        embed = discord.Embed(
            title="⏰ Time's Up!",
            description=f"The game has ended due to inactivity!",
            color=discord.Color.orange()
        )
        
        if len(self.players) > 0:
            # Show all players and their results
            players_text = ""
            for player_id, player_data in self.players.items():
                players_text += f"{player_data['result']} - {player_data['username']} ({player_data['move']} vs {player_data['bot_move']})\n"
            embed.add_field(name="🏆 Final Results", value=players_text, inline=False)
        else:
            embed.add_field(name="Note", value="No players participated", inline=False)
        
        embed.add_field(name="Total Participants", value=str(len(self.players)), inline=True)
        embed.set_footer(text="⏰ Time expired")

        await self.end_game(embed, disable_ui=True)
        
    def create_embed(self) -> discord.Embed:
        """Create the main RPS game embed"""
        embed = discord.Embed(
            title=f"🎮 Rock Paper Scissors",
            description=f"**Game #{self.game_id}**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Choose your move!", 
            value="🪨 **ROCK** | 📄 **PAPER** | ✂️ **SCISSORS**", 
            inline=False
        )
        
        embed.add_field(
            name="How to Play",
            value="Click one of the buttons below to make your move.\nEach player can only play once!",
            inline=False
        )
        
        embed.set_footer(
            text="⏱️ 60 seconds to play • Cancel to end early"
        )

        return embed

# Rock Paper Scissors Game Cog
class Rps(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games = set()  # Track active games to prevent conflicts

    @app_commands.command(name="rock_paper_scissor", description="Start a Rock, Paper, Scissors game")
    async def rock_paper_scisors(self, interaction: discord.Interaction):
        """Start a Rock Paper Scissors game"""
        # Check if there's already an active game in this channel
        channel_id = interaction.channel.id
        if channel_id in self.active_games:
            await interaction.response.send_message(
                "⚠️ There's already an active game in this channel!", 
                ephemeral=True
            )
            return
        
        try:
            # Create view and embed
            view = RpsView(timeout_seconds=60)
            embed = view.create_embed()
            
            # Send message
            await interaction.response.send_message(embed=embed, view=view)
            message = await interaction.original_response()
            
            # Store message reference for later editing
            view.message_ref = message
            
            # Register this game as active
            self.active_games.add(channel_id)
            
            # Clean up when game ends
            async def cleanup():
                await asyncio.sleep(1)  # Small delay to ensure cleanup
                self.active_games.discard(channel_id)
            
            # Schedule cleanup (this will run when the view is finished)
            asyncio.create_task(cleanup())
            
        except Exception as e:
            print(f"Error starting rock, paper, scissor: {e}")
            await interaction.response.send_message(
                "❌ Failed to start game. Please try again.", 
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
    await bot.add_cog(Rps(bot))

