import discord
import random


from discord import app_commands
from discord_secrets import DISCORD_TOKEN

# names cmd window
import ctypes
ctypes.windll.kernel32.SetConsoleTitleW("Tic-Tac-Feet")


# Enable intents with member access
intents = discord.Intents.default()
intents.members = True  # Required for user autocomplete in slash commands


# Store active games keyed by sorted player pair
active_games = {}  # Key: (player1_id, player2_id), Value: game state

# Pass intents to the bot
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        synced = await self.tree.sync()
        print(f"Synced commands: {[cmd.name for cmd in synced]}")
        print(f"Logged in as {self.user}")
       

client = MyClient()




class GameState:
    def __init__(self, player1, player2):
        self.player1 = player1
        self.player2 = player2
        self.current_turn = random.choice([player1, player2])
        self.meta_board = [None] * 9  # Each small board state
        self.tiles = [[None for _ in range(9)] for _ in range(9)]  # 9 boards of 9 tiles
        self.active_board = None  # None = free choice
        self.message = None
        self.meta_winner = None

    
    def check_winner(self, board: list[str | None]) -> str | None:
        win_patterns = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
            [0, 4, 8], [2, 4, 6]              # Diagonals
        ]
        for a, b, c in win_patterns:
            if board[a] and board[a] == board[b] == board[c]:
                return board[a] # "X" or "O"
        return None
        
    def place_tile(self, board_index: int, tile_index: int, symbol: str):
        self.tiles[board_index][tile_index] = symbol

        # Check for win on this small board
        if self.meta_board[board_index] is None:
            winner = self.check_winner(self.tiles[board_index])
            if winner:
                self.meta_board[board_index] = winner

        # 🔥 Check for win on meta board
        meta_winner = self.check_winner(self.meta_board)
        if meta_winner:
            self.meta_winner = meta_winner  # Save the winner to use elsewhere
            return  # Skip further processing

        # Decide next active board
        if self.meta_board[tile_index] is None and any(t is None for t in self.tiles[tile_index]):
            self.active_board = tile_index
        else:
            self.active_board = None





# RENDER LARGE BOARD
    def render_board(self):
        result = ""
        x_pattern = ["❌", "⬛", "❌",
                     "⬛", "❌", "⬛",
                     "❌", "⬛", "❌"]
        o_pattern = ["🟢", "🟢", "🟢",
                     "🟢", "⬛", "🟢",
                     "🟢", "🟢", "🟢"]
        for row in range(3):
            for inner_row in range(3):
                line = ""
                for col in range(3):
                    board_index = row * 3 + col
                    for inner_col in range(3):
                        tile_index = inner_row * 3 + inner_col
                        if self.meta_board[board_index] == "X":
                            emoji = x_pattern[tile_index]
                        elif self.meta_board[board_index] == "O":
                            emoji = o_pattern[tile_index]
                        else:
                            tile = self.tiles[board_index][tile_index]
                            if tile == "X":
                                emoji = "❌"
                            elif tile == "O":
                                emoji = "🟢"
                            elif self.active_board == board_index:
                                emoji = "🟦"
                            else:
                                emoji = "⬛"
                        line += emoji
                    if col < 2:
                        line += " | "
                result += line + "\n"
            if row < 2:
                result += "―" * 16 + "\n"
        return result


class BoardSelectView(discord.ui.View):
    def __init__(self, game: GameState):
        super().__init__(timeout=None)
        self.game = game

        for i in range(9):
            row = i // 3  # row 0 → buttons 0–2, row 1 → 3–5, row 2 → 6–8
            is_disabled = game.meta_board[i] is not None  # disable if board is won
            self.add_item(BoardSelectButton(i, game, row, is_disabled))



class BoardSelectButton(discord.ui.Button):
    def __init__(self, board_index: int, game: GameState, row: int, disabled: bool):
        super().__init__(
            label="🟦",
            style=discord.ButtonStyle.primary,
            row=row,
            disabled=disabled
        )
        self.board_index = board_index
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        # 1) turn-guard
        if interaction.user.id != self.game.current_turn:
            return await interaction.response.send_message(
                "⛔ Not your turn.", ephemeral=True, delete_after=4
            )

        # 2) set active sub-board
        self.game.active_board = self.board_index

        # 3) rebuild board + tile view
        next_symbol = "❌" if self.game.current_turn == self.game.player1 else "🟢"
        content = (
            f"<@{self.game.player1}> vs <@{self.game.player2}>\n"
            f"It's {next_symbol} <@{self.game.current_turn}>'s turn.\n\n"
            f"{self.game.render_board()}\n\u200B"
        )
        new_view = TileSelectView(self.game)

        # 4) *one* call to edit the original message:
        await interaction.response.edit_message(
            content=content,
            view=new_view
        )



class TileSelectView(discord.ui.View):
    def __init__(self, game: GameState):
        super().__init__(timeout=None)
        self.game = game

        if game.active_board is None:
            raise ValueError("TileSelectView should only be used when a specific active_board is set.")
        board_index = game.active_board


        for tile_index in range(9):
            tile_value = game.tiles[board_index][tile_index]
            row = tile_index // 3

            is_clickable = tile_value not in ("X", "O")

            self.add_item(TileSelectButton(tile_index, game, tile_value, row, board_index, active=is_clickable))

class TileSelectButton(discord.ui.Button):
    def __init__(self, tile_index: int, game: GameState, value: str | None, row: int, board_index: int, active: bool):
        label = "\u200B"
        style = discord.ButtonStyle.secondary
        disabled = not active  # disable if this board is not selectable

        if value == "X":
            label = "❌"
            style = discord.ButtonStyle.danger
            disabled = True
        elif value == "O":
            label = "🟢"
            style = discord.ButtonStyle.success
            disabled = True

        super().__init__(label=label, style=style, row=row, disabled=disabled)

        self.tile_index = tile_index
        self.board_index = board_index
        self.game = game

    
    
   
    async def callback(self, interaction: discord.Interaction):
        # 1) Turn‐guard
        if interaction.user.id != self.game.current_turn:
            return await interaction.response.send_message(
                "⛔ Not your turn.", ephemeral=True, delete_after=4
            )

        # 2) Place the tile
        symbol = "X" if self.game.current_turn == self.game.player1 else "O"
        self.game.place_tile(self.board_index, self.tile_index, symbol)
        board_str = self.game.render_board()

        # 3) Check for game end (win or scratch)…
        if self.game.meta_winner:
            # build final content + teardown…
            final = (
                f"<@{self.game.player1}> vs <@{self.game.player2}>\n"
                f"{board_str}\n\n"
                f"🏆 {'❌' if self.game.meta_winner=='X' else '🟢'} "
                f"<@{(self.game.player1 if self.game.meta_winner=='X' else self.game.player2)}> wins!"
            )
            return await interaction.response.edit_message(content=final, view=None)

        if all(cell is not None for cell in self.game.meta_board):
            # scratch
            final = f"{board_str}\n\n🤝 It's a scratch!"
            return await interaction.response.edit_message(content=final, view=None)

        # 4) No end → switch turns
        self.game.current_turn = (
            self.game.player2 if self.game.current_turn == self.game.player1
            else self.game.player1
        )
        next_emoji = "❌" if self.game.current_turn == self.game.player1 else "🟢"

        # 5) Build next‐turn content + view
        content = (
            f"<@{self.game.player1}> vs <@{self.game.player2}>\n"
            f"It's {next_emoji} <@{self.game.current_turn}>'s turn.\n\n"
            f"{board_str}\n\u200B"
        )
        new_view = (
            BoardSelectView(self.game) if self.game.active_board is None
            else TileSelectView(self.game)
        )

        # 6) Single edit to original message
        await interaction.response.edit_message(content=content, view=new_view)

       

# PLAY COMMAND 
@client.tree.command(name="play", description="Start a full Tic-Tac-Feet game with your opponent")
@app_commands.describe(opponent="The user you are playing against")
async def play(interaction: discord.Interaction, opponent: discord.User):
    # 1) Channel guard
    if interaction.channel.name != "tic-tac-feet":
        return await interaction.response.send_message(
            "⛔ This game can only be played in #tic-tac-feet.",
            ephemeral=True,
            delete_after=4
        )

    # 2) Can't play yourself
    if interaction.user.id == opponent.id:
        return await interaction.response.send_message(
            "😅 You can't play against yourself!", ephemeral=True, delete_after=4
        )

    # 3) Already playing?
    game_key = tuple(sorted((interaction.user.id, opponent.id)))
    if game_key in active_games:
        return await interaction.response.send_message(
            "⚠️ You already have an active game with this player.",
            ephemeral=True,
            delete_after=4
        )

    # 4) Initialize game state + view
    game = GameState(interaction.user.id, opponent.id)
    view = BoardSelectView(game)
    content = (
        f"🎮 <@{game.player1}> vs <@{game.player2}>\n"
        f"<@{game.current_turn}> goes first!\n\n"
        f"{game.render_board()}\n\u200B"
    )

    # 5) Send the game board as the *initial* response
    await interaction.response.send_message(content=content, view=view)

    # 6) Grab that message so we can edit it later
    game.message = await interaction.original_response()

    # 7) Store in active_games
    active_games[game_key] = game






# RESIGN COMMAND
@client.tree.command(name="resign", description="Resign from your current Tic-Tac-Feet game")
async def resign(interaction: discord.Interaction):
    if interaction.channel.name != "tic-tac-feet":
        await interaction.response.send_message("⛔ This command only works in #tic-tac-feet.", ephemeral=True, delete_after=4)
        return
    user_id = interaction.user.id

    # Try to find the user's game
    for key in list(active_games.keys()):
        if user_id in key:
            # Found the game
            opponent_id = key[0] if key[1] == user_id else key[1]
            game = active_games.pop(key, None)
            
            # Disable game board buttons
            if game.message:
                await game.message.edit(view=discord.ui.View(timeout=0))

            await interaction.response.send_message(
                f"🏳️ <@{user_id}> has resigned. <@{opponent_id}> wins by forfeit!")
            return

    # No game found
    await interaction.response.send_message(
        "⚠️ You are not currently in an active game.",
        ephemeral=True,
        delete_after=4
    )




client.run(DISCORD_TOKEN)