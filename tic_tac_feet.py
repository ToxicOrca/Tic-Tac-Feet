import discord
from discord import app_commands
from discord.ext import tasks
from secrets import DISCORD_TOKEN


# Enable intents with member access
intents = discord.Intents.default()
intents.members = True  # Required for user autocomplete in slash commands


# Store active games
active_games = {}  # Key: channel_id, Value: (player1_id, player2_id, current_turn, board)

# Pass intents to the bot
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        synced = await self.tree.sync()
        print(f"Logged in as {self.user} and synced commands.")

client = MyClient()

@client.tree.command(name="start", description="Start a new game of Tic-Tac-Feet")
async def start(interaction: discord.Interaction):
    await interaction.response.send_message("🎮 Tic-Tac-Feet game started!", ephemeral=False)

@client.tree.command(name="challenge", description="Challenge another player to Tic-Tac-Toe")
@app_commands.describe(opponent="The user you want to challenge")
async def challenge(interaction: discord.Interaction, opponent: discord.User):
    channel_id = interaction.channel_id

    if channel_id in active_games:
        await interaction.response.send_message("⚠️ A game is already in progress in this channel!", ephemeral=True)
        return

    if opponent.id == interaction.user.id:
        await interaction.response.send_message("😅 You can't challenge yourself!", ephemeral=True)
        return

    # Initialize game board (list of 9 empty strings)
    board = [" " for _ in range(9)]

    active_games[channel_id] = {
        "player1": interaction.user.id,
        "player2": opponent.id,
        "turn": interaction.user.id,
        "board": board
    }

    await interaction.response.send_message(
        f"🎮 {interaction.user.mention} has challenged {opponent.mention} to a game of Tic-Tac-Toe!\n"
        f"{interaction.user.mention} goes first. Use `/play position:` to make your move (1-9)."
    )

client.run(DISCORD_TOKEN)
