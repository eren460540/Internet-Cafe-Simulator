import os
import discord
from discord.ext import commands

# Note: if there will be used the word "cafe" it msut be "Café"

# ===== RAILWAY ENV CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"

# ===== COLORS =====
CYBER_DARK = 0x0b0f1a
CYBER_CYAN = 0x1ae4ff

# ===== INTENTS =====
intents = discord.Intents.default()
intents.message_content = True

# ===== BOT INSTANCE =====
bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents
)

# ===== UI COMPONENTS =====
class ControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        button_style = discord.ButtonStyle.secondary
        # Row 1
        self.add_item(discord.ui.Button(style=button_style, emoji="🖥️", label="", disabled=True))
        self.add_item(discord.ui.Button(style=button_style, emoji="🎮", label="", disabled=True))
        self.add_item(discord.ui.Button(style=button_style, emoji="🧍", label="", disabled=True))
        self.add_item(discord.ui.Button(style=button_style, emoji="👨‍💼", label="", disabled=True))
        self.add_item(discord.ui.Button(style=button_style, emoji="💰", label="", disabled=True))
        # Row 2
        self.add_item(discord.ui.Button(style=button_style, emoji="⭐", label="", disabled=True))
        self.add_item(discord.ui.Button(style=button_style, emoji="⚡", label="", disabled=True))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.danger, emoji="☣️", label="", disabled=True))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.primary, emoji="🏆", label="", disabled=True))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.primary, emoji="⚙️", label="", disabled=True))


# ===== EMBED BUILDERS =====
def build_cafe_embed():
    embed = discord.Embed(
        title="☕ INTERNET CAFÉ CONTROL PANEL",
        description="Neon Byte Café | Level 3 | Status: OPEN",
        color=CYBER_CYAN
    )

    embed.add_field(
        name="SECTION 1 — SYSTEM STATUS",
        value=(
            "💻 PCs: 18\n"
            "🔥 Overheating: 2\n"
            "❌ Broken: 1\n\n"
            "🌐 Internet Speed: Stable\n"
            "⚡ Electricity Load: 67%"
        ),
        inline=False
    )

    embed.add_field(
        name="SECTION 2 — CUSTOMERS",
        value=(
            "🧍 Active: 24\n"
            "😡 Angry: 3\n"
            "🎮 Hardcore Gamers: 7\n"
            "🕵️ Suspicious Users: 2"
        ),
        inline=False
    )

    embed.add_field(
        name="SECTION 3 — STAFF",
        value=(
            "👨‍💼 Total Staff: 6\n"
            "😴 Lazy: 1\n"
            "💰 Corrupt: 1\n"
            "🧠 Skilled: 3"
        ),
        inline=False
    )

    embed.add_field(
        name="SECTION 4 — FINANCE",
        value=(
            "💵 Cash: $12,480\n"
            "📈 Daily Profit: +$860\n"
            "📉 Bills: -$430"
        ),
        inline=False
    )

    embed.add_field(
        name="SECTION 5 — REPUTATION",
        value=(
            "⭐ Rating: 3.9/5\n"
            "📝 Latest Review:\n"
            '"PC lagged, keyboard sticky, owner vanished."'
        ),
        inline=False
    )

    embed.add_field(
        name="SECTION 6 — ALERTS (HIGH VISIBILITY)",
        value=(
            "⚠️ Virus detected on PC-03\n"
            "🔥 Fire risk CRITICAL\n"
            "🚓 Police attention: MEDIUM"
        ),
        inline=False
    )

    embed.set_footer(text="CafeOS v6.6 | Memory Leak Detected | Chaos Level: HIGH")
    embed.set_author(name="Cyberpunk HUD", icon_url="https://emoji.discord.st/emojis/8254d7bf-2efc-4b43-9f8b-69b3a7be3c7e.png")
    return embed


def build_help_embed():
    embed = discord.Embed(
        title="📘 INTERNET CAFÉ SIMULATOR — HELP",
        description=(
            "Welcome to Internet Café Simulator on Discord.\n"
            "You are the owner of a chaotic, neon-lit gaming Café.\n"
            "Your goal is to survive, grow, and dominate."
        ),
        color=CYBER_DARK
    )

    embed.add_field(
        name="GETTING STARTED",
        value="☕ !cafe\nOpen your café control panel and manage everything from one place.",
        inline=False
    )

    embed.add_field(
        name="CORE SYSTEMS",
        value=(
            "🖥️ PCs — Buy, upgrade, repair computers\n"
            "🎮 Games — Install games to attract customers\n"
            "🧍 Customers — Manage behavior and chaos\n"
            "👨‍💼 Staff — Hire workers to automate tasks\n"
            "💰 Money — Track income and bills\n"
            "⭐ Reputation — Reviews affect everything\n"
            "⚡ Utilities — Electricity and internet stability\n"
            "☣️ Crime — Risky actions with big rewards\n"
            "🏆 Leaderboards — Compare with others"
        ),
        inline=False
    )

    embed.add_field(
        name="IMPORTANT TIPS",
        value=(
            "- Cheap hardware breaks faster\n"
            "- Dirty cafés get bad reviews\n"
            "- Illegal actions attract police\n"
            "- Chaos is part of the game"
        ),
        inline=False
    )

    embed.add_field(
        name="FINAL NOTE",
        value=(
            "This bot is a living simulation.\n"
            "Things WILL go wrong.\n"
            "That’s the fun."
        ),
        inline=False
    )

    embed.set_footer(text="Tutorial compiled by Neon Desk AI — Stay chaotic.")
    return embed


# ===== COMMANDS =====
@bot.command(name="cafe")
async def cafe_command(ctx: commands.Context):
    embed = build_cafe_embed()
    view = ControlPanelView()
    await ctx.send(embed=embed, view=view)


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    embed = build_help_embed()
    await ctx.send(embed=embed)


# ===== READY EVENT =====
@bot.event
async def on_ready():
    print("===================================")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("Internet Café Simulator — Discord Edition booted")
    print("===================================")


# ===== RUN BOT =====
bot.run(TOKEN)
