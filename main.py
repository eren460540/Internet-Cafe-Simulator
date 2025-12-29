import discord
from discord.ext import commands
import os

# ===== RAILWAY ENV CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"

# ===== INTENTS =====
intents = discord.Intents.default()
intents.message_content = True

# ===== BOT INSTANCE =====
bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)

# ===== READY EVENT =====
@bot.event
async def on_ready():
    print("===================================")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("Internet Cafe Bot TEMPLATE running")
    print("===================================")

# ===== RUN BOT =====
bot.run(TOKEN)
