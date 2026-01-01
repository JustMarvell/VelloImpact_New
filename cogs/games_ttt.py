# Tick, Tack, Toe game

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
from typing import Dict, Optional
import uuid

# Game states
class GameState:
    ACTIVE = "active"
    ENDED = "ended"
    CANCELLED = "cancelled"

# Player markers
class Player:
    X = "❌"
    O = "⭕"

# Winning combinations
WINNING_COMBINATIONS = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Columns
    (0, 4, 8), (2, 4, 6),              # Diagonals
]


class TicTacToeAI:
    """AI opponent with moderate to hard difficulty"""
    
    def __init__(self, ai_marker: str, opponent_marker: str):
        self.ai_marker = ai_marker
        self.opponent_marker = opponent_marker
    
    def get_best_move(self, board: list) -> Optional[int]:
        """Get the best move for the AI using minimax-like strategy"""
        available_moves = [i for i, cell in enumerate(board) if cell is None]
        
        if not available_moves:
            return None
        
        # 1. Win immediately if possible
        for move in available_moves:
            board_copy = board.copy()
            board_copy[move] = self.ai_marker
            if self._check_winner(board_copy) == self.ai_marker:
                return move
        
        # 2. Block opponent's winning move
        for move in available_moves:
            board_copy = board.copy()
            board_copy[move] = self.opponent_marker
            if self._check_winner(board_copy) == self.opponent_marker:
                return move
        
        # 4. Take corners (in order of priority)
        corners = [0, 2, 6, 8]
        available_corners = [c for c in corners if c in available_moves]
        if available_corners:
            return random.choice(available_corners)
        
        # 5. Take sides
        sides = [1, 3, 5, 7]
        available_sides = [s for s in sides if s in available_moves]
        if available_sides:
            return random.choice(available_sides)
        
        # 3. Take center if available
        if 4 in available_moves:
            return 4
        
        
        # Fallback: random move
        return random.choice(available_moves)
    
    def _check_winner(self, board: list) -> Optional[str]:
        """Check if there's a winner on the board"""
        for combo in WINNING_COMBINATIONS:
            a, b, c = combo
            if board[a] is not None and board[a] == board[b] == board[c]:
                return board[a]
        return None


class TickView(discord.ui.View):
    def __init__(self, cog, player_a: discord.Member, player_b: discord.Member, timeout_seconds: int = 300, is_bot_game: bool = False):
        super().__init__(timeout=timeout_seconds)
        
        # Reference to cog for cleanup
        self._cog = cog
        self.is_bot_game = is_bot_game
        
        # Game state
        self.game_id = str(uuid.uuid4())[:8]
        self.game_state = GameState.ACTIVE
        self.timer_task = None
        self.seconds_left = timeout_seconds
        self.message_ref = None
        
        # Randomize who goes first (X goes first)
        if random.choice([True, False]):
            # player_a goes first as X, player_b goes second as O
            self.x_player = player_a
            self.o_player = player_b
        else:
            # player_b goes first as X, player_a goes second as O
            self.x_player = player_b
            self.o_player = player_a
        
        self.x_player_id = self.x_player.id
        self.o_player_id = self.o_player.id
        self.current_turn = self.x_player  # X goes first
        
        # Bot AI (if applicable)
        self.ai = None
        self.bot_marker = None
        if is_bot_game:
            # Bot uses the marker of whichever player slot it was assigned to
            if self.o_player_id == cog.bot.user.id:
                self.bot_marker = Player.O
                self.ai = TicTacToeAI(ai_marker=Player.O, opponent_marker=Player.X)
            else:
                self.bot_marker = Player.X
                self.ai = TicTacToeAI(ai_marker=Player.X, opponent_marker=Player.O)
        
        # Board: 9 cells
        self.board = [None] * 9
        
        # Create buttons
        self._create_buttons()
    
    def _create_buttons(self):
        """Create all game buttons"""
        for i in range(9):
            btn = discord.ui.Button(
                label="‎ ", 
                style=discord.ButtonStyle.secondary,
                custom_id=f"ttt_{i}",
                row=i // 3
            )
            btn.callback = self._button_callback
            self.add_item(btn)
        
        # Cancel button
        cancel_btn = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.red,
            custom_id="ttt_cancel",
            row=3
        )
        cancel_btn.callback = self._cancel_callback
        self.add_item(cancel_btn)
    
    def disable_all_components(self):
        for child in self.children:
            child.disabled = True
    
    def _cleanup_game(self):
        """Remove this game from active_games"""
        if self._cog and self.message_ref:
            self._cog.active_games.pop(self.message_ref.id, None)
    
    def _get_player_by_id(self, user_id: int) -> discord.Member:
        """Get player by ID"""
        if user_id == self.x_player_id:
            return self.x_player
        return self.o_player
    
    def _get_marker_for_user(self, user_id: int) -> str:
        """Get the marker for a user"""
        return Player.X if user_id == self.x_player_id else Player.O
    
    def _get_current_marker(self) -> str:
        """Get current player's marker"""
        return Player.X if self.current_turn.id == self.x_player_id else Player.O
    
    async def check_winner(self) -> Optional[tuple]:
        for combo in WINNING_COMBINATIONS:
            a, b, c = combo
            if self.board[a] is not None and self.board[a] == self.board[b] == self.board[c]:
                return (self.board[a], combo)
        return None
    
    def is_board_full(self) -> bool:
        return all(cell is not None for cell in self.board)
    
    async def _make_bot_move(self):
        """Make the bot's move after a delay"""
        if self.game_state != GameState.ACTIVE:
            return
        
        # Wait for message_ref to be set
        if self.message_ref is None:
            await asyncio.sleep(0.2)
        
        if self.game_state != GameState.ACTIVE or self.message_ref is None:
            return
        
        await asyncio.sleep(0.5)  # Small delay for realism
        
        # Check if game still active
        if self.game_state != GameState.ACTIVE:
            return
        
        # Get bot's move
        move = self.ai.get_best_move(self.board)
        
        if move is not None:
            self.board[move] = self.bot_marker
            
            # Update button display
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.custom_id == f"ttt_{move}":
                    child.label = self.bot_marker
                    child.style = discord.ButtonStyle.primary if self.bot_marker == Player.X else discord.ButtonStyle.success
                    child.disabled = True
                    break
            
            # Check for winner
            winner_result = await self.check_winner()
            
            if winner_result:
                winner_marker, _ = winner_result
                winner = self.x_player.mention if winner_marker == Player.X else self.o_player.mention
                
                embed = discord.Embed(
                    title="Tic-Tac-Toe - Winner!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Winner", value=f"{winner}")
                embed.add_field(name="Board", value=self._format_board())
                
                self.disable_all_components()
                self.game_state = GameState.ENDED
                self._cleanup_game()
                
                await self.message_ref.edit(embed=embed, view=self)
                return
            
            # Check for draw
            if self.is_board_full():
                embed = discord.Embed(
                    title="Tic-Tac-Toe - Draw!",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Result", value="Draw!")
                embed.add_field(name="Board", value=self._format_board())
                
                self.disable_all_components()
                self.game_state = GameState.ENDED
                self._cleanup_game()
                
                await self.message_ref.edit(embed=embed, view=self)
                return
            
            # Switch turn to the other player
            self.current_turn = self.o_player if self.current_turn.id == self.x_player_id else self.x_player
            
            # Update embed
            embed = self._create_embed()
            embed.set_field_at(1, name="Current Turn", value=f"{self.current_turn.mention} ({self._get_current_marker()})")
            
            await self.message_ref.edit(embed=embed, view=self)
    
    async def _button_callback(self, interaction: discord.Interaction):
        position = int(interaction.data['custom_id'].split("_")[1])
        
        if self.game_state != GameState.ACTIVE:
            await interaction.response.send_message("Game already ended!", ephemeral=True)
            return
        
        user_id = interaction.user.id
        
        # In bot games, only the human player can move
        if self.is_bot_game:
            if user_id != self.x_player_id and user_id != self.o_player_id:
                await interaction.response.send_message("Not a player in this game!", ephemeral=True)
                return
        
        # Check if it's this player's turn
        if user_id != self.current_turn.id:
            await interaction.response.send_message(f"It's {self.current_turn.mention}'s turn!", ephemeral=True)
            return
        
        if self.board[position] is not None:
            await interaction.response.send_message("Cell already taken!", ephemeral=True)
            return
        
        # Make the move
        marker = self._get_current_marker()
        self.board[position] = marker
        
        # Update button display
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == f"ttt_{position}":
                child.label = marker
                child.style = discord.ButtonStyle.primary if marker == Player.X else discord.ButtonStyle.success
                child.disabled = True
                break
        
        await interaction.response.defer()
        
        # Check for winner
        winner_result = await self.check_winner()
        
        if winner_result:
            winner_marker, _ = winner_result
            winner = self.x_player.mention if winner_marker == Player.X else self.o_player.mention
            
            embed = discord.Embed(
                title="Tic-Tac-Toe - Winner!",
                color=discord.Color.green()
            )
            embed.add_field(name="Winner", value=f"{winner}")
            embed.add_field(name="Board", value=self._format_board())
            
            self.disable_all_components()
            self.game_state = GameState.ENDED
            self._cleanup_game()
            
            await self.message_ref.edit(embed=embed, view=self)
            return
        
        # Check for draw
        if self.is_board_full():
            embed = discord.Embed(
                title="Tic-Tac-Toe - Draw!",
                color=discord.Color.gold()
            )
            embed.add_field(name="Result", value="Draw!")
            embed.add_field(name="Board", value=self._format_board())
            
            self.disable_all_components()
            self.game_state = GameState.ENDED
            self._cleanup_game()
            
            await self.message_ref.edit(embed=embed, view=self)
            return
        
        # Switch turns
        self.current_turn = self.o_player if self.current_turn.id == self.x_player_id else self.x_player
        
        # Update embed
        embed = self._create_embed()
        embed.set_field_at(1, name="Current Turn", value=f"{self.current_turn.mention} ({self._get_current_marker()})")
        
        await self.message_ref.edit(embed=embed, view=self)
        
        # If bot game and it's now bot's turn, make bot move
        if self.is_bot_game and self.game_state == GameState.ACTIVE:
            # Check if it's the bot's turn (either X or O)
            is_bot_turn = (self.current_turn.id == self.x_player_id and self.x_player_id == self._cog.bot.user.id) or \
                         (self.current_turn.id == self.o_player_id and self.o_player_id == self._cog.bot.user.id)
            if is_bot_turn:
                asyncio.create_task(self._make_bot_move())
    
    async def _cancel_callback(self, interaction: discord.Interaction):
        if self.game_state != GameState.ACTIVE:
            await interaction.response.send_message("Game already ended!", ephemeral=True)
            return

        embed = discord.Embed(
            title="Game Cancelled",
            description=f"Cancelled by {interaction.user.mention}",
            color=discord.Color.greyple()
        )
        embed.add_field(name="Board", value=self._format_board())
        
        await interaction.response.defer()
        await self._end_game(embed, disable_ui=False)
    
    async def _end_game(self, embed: discord.Embed, disable_ui: bool = True):
        if self.game_state != GameState.ACTIVE:
            return
        
        self.game_state = GameState.ENDED
        
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        
        if disable_ui:
            self.disable_all_components()
        
        # Cleanup from active games
        self._cleanup_game()
        
        if self.message_ref:
            try:
                await self.message_ref.edit(embed=embed, view=self if disable_ui else None)
            except discord.errors.NotFound:
                pass
    
    async def on_timeout(self):
        if self.game_state != GameState.ACTIVE:
            return
        
        embed = discord.Embed(
            title="Time's Up!",
            description="Game ended due to inactivity",
            color=discord.Color.orange()
        )
        embed.add_field(name="Board", value=self._format_board())
        
        await self._end_game(embed, disable_ui=True)
    
    def _format_board(self) -> str:
        lines = []
        for row in range(3):
            cells = []
            for col in range(3):
                pos = row * 3 + col
                cell = self.board[pos]
                if cell is None:
                    cells.append("⬛")
                else:
                    cells.append(cell)
            lines.append(" ".join(cells))
        return "\n".join(lines)
    
    def _create_embed(self) -> discord.Embed:
        opponent_name = "Bot" if self.is_bot_game else str(self.o_player)
        
        embed = discord.Embed(
            title="Tic-Tac-Toe",
            color=discord.Color.blue()
        )
        
        # Show who is X and who is O
        embed.add_field(
            name="Players",
            value=f"❌: {self.x_player}\n⭕: {opponent_name}",
            inline=True
        )
        
        embed.add_field(
            name="Current Turn",
            value=f"{self.current_turn.mention} ({self._get_current_marker()})",
            inline=False
        )
        
        if self.is_bot_game:
            embed.add_field(
                name="vs",
                value="You are playing against the Bot!",
                inline=False
            )
        
        embed.set_footer(text="5 minutes to play")
        
        return embed


class TickTackToe(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games = {}
        
    @app_commands.command(name="tick_tack_toe", description="Start a Tic-Tac-Toe game. Mention a user or the bot to play against them!")
    @app_commands.describe(
        opponent = "Member to be opponent (Mention the bot to play against the bot)"
    )
    async def tick_tack_toe(self, interaction: discord.Interaction, opponent: discord.Member):
        """Start a Tic-Tac-Toe game against a player or the bot"""
        user_id = interaction.user.id
        opponent_id = opponent.id
        
        # Check if opponent is the bot
        is_bot_game = (opponent_id == self.bot.user.id)
        
        # Prevent self-play (unless playing against bot)
        if user_id == opponent_id and not is_bot_game:
            await interaction.response.send_message("Cannot play against yourself!", ephemeral=True)
            return
        
        # Check for active games
        for game_id, game_data in self.active_games.items():
            p1_id = game_data['view'].x_player_id
            p2_id = game_data['view'].o_player_id
            if user_id in [p1_id, p2_id] or opponent_id in [p1_id, p2_id]:
                await interaction.response.send_message("Player already in an active game!", ephemeral=True)
                return
        
        try:
            view = TickView(
                cog=self,
                player_a=interaction.user,
                player_b=opponent,
                timeout_seconds=300,
                is_bot_game=is_bot_game
            )
            
            embed = view._create_embed()
            
            await interaction.response.send_message(embed=embed, view=view)
            message = await interaction.original_response()
            
            view.message_ref = message
            
            self.active_games[message.id] = {
                'player1': interaction.user,
                'player2': opponent,
                'view': view,
                'is_bot_game': is_bot_game
            }
            
            # If bot game and bot is supposed to go first (bot is x_player), make bot move
            if is_bot_game and view.x_player_id == self.bot.user.id:
                asyncio.create_task(view._make_bot_move())
            
        except Exception as e:
            print(f"Error: {e}")
            await interaction.response.send_message("Failed to start game.", ephemeral=True)

    async def cog_unload(self):
        for game_data in self.active_games.values():
            view = game_data['view']
            if view.timer_task and not view.timer_task.done():
                view.timer_task.cancel()
        self.active_games.clear()


async def setup(bot: commands.Bot):
    await bot.add_cog(TickTackToe(bot))

