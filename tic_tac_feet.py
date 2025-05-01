import discord
import random


from discord import app_commands
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

# RENDER LARGE BOARD
def render_meta_board(meta_board: list[str | None], active_board: int) -> str:
    result = ""
    for row in range(3):
        for inner_row in range(3):
            line = ""
            for col in range(3):
                board_index = row * 3 + col
                for inner_col in range(3):
                    # Placeholder tile display
                    if meta_board[board_index] == "X":
                        emoji = "❌"
                    elif meta_board[board_index] == "O":
                        emoji = "🟢"
                    elif active_board is not None and board_index == active_board:
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



class TicTacFeetLocalButton(discord.ui.Button):
    def __init__(self, tile_index: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="\u200b",
            row=tile_index // 3
        )
        self.tile_index = tile_index

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"You clicked tile {self.tile_index} in the active board!",
            ephemeral=True,
            delete_after=2
        )


class TicTacFeetLocalBoardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for i in range(9):
            self.add_item(TicTacFeetLocalButton(i))


class TicTacFeetButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacFeetView = self.view
        player = interaction.user

        # Prevent wrong player from moving
        if player.id != view.current_turn:
            await interaction.response.send_message("⛔ It's not your turn!", ephemeral=True, delete_after=2)
            return

        # Mark the cell
        symbol = "X" if player.id == view.player1 else "O"
        self.label = symbol
        self.style = discord.ButtonStyle.danger if symbol == "X" else discord.ButtonStyle.success
        self.disabled = True
        view.board[self.y][self.x] = symbol
        await interaction.response.edit_message(view=view)

        # Check for win
        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True
                
            # clean up
            game_key = tuple(sorted((view.player1, view.player2)))
            active_games.pop(game_key, None)

            # Determine who won
            winner_id = view.player1 if winner == "X" else view.player2
            await interaction.followup.send(f"🏆 <@{winner_id}> wins!")
            await interaction.message.edit(view=view)  # Update disabled board
            return
        
        # Check for tie
        if view.check_tie():
            for child in view.children:
                child.disabled = True
            
            # clean up
            game_key = tuple(sorted((view.player1, view.player2)))
            active_games.pop(game_key, None)
            
            await interaction.followup.send(f"🤝 <@{view.player1}> and <@{view.player2}> tied!")
            await interaction.message.edit(view=view)
            return

        # Switch turns
        view.current_turn = view.player2 if player.id == view.player1 else view.player1


class TicTacFeetView(discord.ui.View):
    def __init__(self, player1: int, player2: int):
        super().__init__(timeout=None)
        self.player1 = player1
        self.player2 = player2
        self.current_turn = random.choice([player1, player2])
        self.board = [["" for _ in range(3)] for _ in range(3)]

        for y in range(3):
            for x in range(3):
                self.add_item(TicTacFeetButton(x, y))

    def check_winner(self):
        # Horizontal, Vertical, Diagonal
        lines = []

        # Rows and columns
        for i in range(3):
            lines.append(self.board[i])  # rows
            lines.append([self.board[0][i], self.board[1][i], self.board[2][i]])  # cols

        # Diagonals
        lines.append([self.board[0][0], self.board[1][1], self.board[2][2]])
        lines.append([self.board[0][2], self.board[1][1], self.board[2][0]])

        for line in lines:
            if line[0] != "" and all(cell == line[0] for cell in line):
                return line[0]
        return None

    def check_tie(self):
        return all(cell != "" for row in self.board for cell in row)


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

    # Initialize game state
    meta_board = [None] * 9
    active_board = None  # No board is active until the first move

    # Render visual board
    visual = render_meta_board(meta_board, active_board)
    view = TicTacFeetLocalBoardView()

    active_games[game_key] = {
        "meta_board": meta_board,
        "active_board": active_board,
        "current_turn": random.choice(game_key),
    }

    await interaction.response.send_message(
        content=f"🎮 **Tic-Tac-Feet**: <@{interaction.user.id}> vs <@{opponent.id}>\n"
                f"<@{active_games[game_key]['current_turn']}> goes first!\n\n"
                f"{visual}",
        view=view
    )



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



class TicTacFeetTileButton(discord.ui.Button):
    def __init__(self, board_index: int, tile_index: int, active: bool):
        # Each board has 3 rows, so this spreads them out
        row = (board_index // 3) * 3 + (tile_index // 3)
        col = (board_index % 3) * 3 + (tile_index % 3)

        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="\u200b",
            row=row
        )
        
        self.board_index = board_index
        self.tile_index = tile_index
        self.disabled = not active

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"You clicked tile {self.tile_index} in board {self.board_index}",
            ephemeral=True,
            delete_after=3
        )



class TicTacFeetGameView(discord.ui.View):
    def __init__(self, player1: int, player2: int):
        super().__init__(timeout=None)
        self.player1 = player1
        self.player2 = player2
        self.current_turn = random.choice([player1, player2])
        self.active_board = 4  # Default to center board

        # Generate 9 boards, each with 9 tiles
        for board_index in range(9):
            for tile_index in range(9):
                is_active = (board_index == self.active_board)
                self.add_item(TicTacFeetTileButton(board_index, tile_index, active=is_active))



client.run(DISCORD_TOKEN)