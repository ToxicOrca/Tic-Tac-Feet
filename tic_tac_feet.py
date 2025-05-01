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
        print(f"Logged in as {self.user} and synced commands.")

client = MyClient()




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


# /play command set up
@client.tree.command(name="play", description="Start an interactive Tic-Tac-Feet game with your opponent")
@app_commands.describe(opponent="The user you are playing against")
async def play(interaction: discord.Interaction, opponent: discord.User):
    if interaction.user.id == opponent.id:
        await interaction.response.send_message("😅 You can't play against yourself!", ephemeral=True, delete_after=4)
        return

    # Sort the player IDs to create a consistent key
    game_key = tuple(sorted((interaction.user.id, opponent.id)))

    # Prevent duplicate games
    if game_key in active_games:
        await interaction.response.send_message("⚠️ You already have an active game with this player.", ephemeral=True, delete_after=4)
        return

    # Create game and view
    view = TicTacFeetView(interaction.user.id, opponent.id)
    active_games[game_key] = view  # You can store the view or game metadata here

    await interaction.response.send_message(
        f"🎮 Tic-Tac-Feet: <@{interaction.user.id}> vs <@{opponent.id}>!\n"
        f"<@{view.current_turn}> goes first!",
        view=view,
        delete_after=60 * 10  # Board disappears after 10 minutes
    )


client.run(DISCORD_TOKEN)