import discord
import random


from discord import app_commands
# allegedly can remove
from discord.ext import tasks

from secrets import DISCORD_TOKEN


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



# RENDER LARGE BOARD
    def render_board(self):
        result = ""
        for row in range(3):
            for inner_row in range(3):
                line = ""
                for col in range(3):
                    board_index = row * 3 + col
                    for inner_col in range(3):
                        tile_index = inner_row * 3 + inner_col
                        tile = self.tiles[board_index][tile_index]
                        if tile == "X":
                            emoji = "❌"
                        elif tile == "O":
                            emoji = "🟢"
                        elif self.active_board == board_index:
                            emoji = "🟨"
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
            self.add_item(BoardSelectButton(i, game))


class BoardSelectButton(discord.ui.Button):
    def __init__(self, board_index: int, game: GameState):
        super().__init__(label=str(board_index), style=discord.ButtonStyle.primary, row=board_index // 3)
        self.board_index = board_index
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.game.current_turn:
            await interaction.response.send_message("⛔ Not your turn.", ephemeral=True, delete_after=4)
            return

        self.game.active_board = self.board_index
        
        await interaction.response.defer()  # 👈 tells Discord “I got this!”
        
        content = f"<@{self.game.player1}> vs <@{self.game.player2}>\n"
        content += f"It's <@{self.game.current_turn}>'s turn.\n\n"
        content += self.game.render_board() + "\n​"
        await self.game.message.edit(content=content, view=TileSelectView(self.game))


class TileSelectView(discord.ui.View):
    def __init__(self, game: GameState):
        super().__init__(timeout=None)
        self.game = game
        for i in range(9):
            if self.game.tiles[self.game.active_board][i] is None:
                self.add_item(TileSelectButton(i, game))


class TileSelectButton(discord.ui.Button):
    def __init__(self, tile_index: int, game: GameState):
        super().__init__(label=str(tile_index), style=discord.ButtonStyle.secondary, row=tile_index // 3)
        self.tile_index = tile_index
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.game.current_turn:
            await interaction.response.send_message("⛔ Not your turn.", ephemeral=True, delete_after=4)
            return

        board = self.game.active_board
        self.game.tiles[board][self.tile_index] = "X" if self.game.current_turn == self.game.player1 else "O"

        # Update next active board
        next_board = self.tile_index
        # If the next board is full, allow free board selection
        if any(tile is None for tile in self.game.tiles[next_board]):
            self.game.active_board = next_board
        else:
            self.game.active_board = None  # Open play

        # Switch turn
        self.game.current_turn = self.game.player2 if self.game.current_turn == self.game.player1 else self.game.player1

        await interaction.response.defer()  # 👈 tells Discord “I got this!”
        
        # Update message
        content = f"🎮 <@{self.game.player1}> vs <@{self.game.player2}>\n"
        content += f"It's <@{self.game.current_turn}>'s turn.\n\n"
        content += self.game.render_board() + "\n\u200B"

        if self.game.active_board is None:
            # Let the next player choose any board
            await self.game.message.edit(content=content, view=BoardSelectView(self.game))
        else:
            # Only show buttons for the active board
            await self.game.message.edit(content=content, view=TileSelectView(self.game))
        

# PLAY COMMAND 
@client.tree.command(name="play", description="Start a full Tic-Tac-Feet game with your opponent")
@app_commands.describe(opponent="The user you are playing against")
async def play(interaction: discord.Interaction, opponent: discord.User):
    if interaction.user.id == opponent.id:
        await interaction.response.send_message("😅 You can't play against yourself!", ephemeral=True, delete_after=4)
        return

    game_key = tuple(sorted((interaction.user.id, opponent.id)))
    if game_key in active_games:
        await interaction.response.send_message("⚠️ You already have an active game with this player.", ephemeral=True, delete_after=4)
        return

    game = GameState(interaction.user.id, opponent.id)
    view = BoardSelectView(game)
    content = f"🎮 <@{game.player1}> vs <@{game.player2}>\n"
    content += f"<@{game.current_turn}> goes first!\n\n"
    content += game.render_board() + "\n\u200B"

    message = await interaction.response.send_message(content=content, view=view)
    game.message = await interaction.original_response()

    active_games[game_key] = game




# RESIGN COMMAND
@client.tree.command(name="resign", description="Resign from your current Tic-Tac-Feet game")
async def resign(interaction: discord.Interaction):
    user_id = interaction.user.id

    # Try to find the user's game
    for key in list(active_games.keys()):
        if user_id in key:
            # Found the game
            opponent_id = key[0] if key[1] == user_id else key[1]
            active_games.pop(key, None)

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