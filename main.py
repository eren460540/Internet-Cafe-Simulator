import json
import os
import random
import time
from copy import deepcopy

import discord
from discord.ext import commands

# Note: if there will be used the word "cafe" it must be "Café"

# ===== RAILWAY ENV CONFIG =====
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"

# ===== SETTINGS =====
# Allow disabling the message content intent (required for prefix commands)
# when it is not enabled in the Discord developer portal. Default to disabled
# so the bot can start even if the privilege is not configured.
MESSAGE_CONTENT_INTENT = os.getenv("DISCORD_MESSAGE_CONTENT_INTENT", "false").lower() == "true"

# ===== FILE STORAGE =====
DATA_FILE = "data.json"
DEFAULT_STATE = {
    "money": 60,
    "reputation": 50,
    "pcs": 1,
    "broken_pcs": 0,
    "is_open": True,
    "last_event": "Your Neon Byte Café just opened its doors.",
    "last_serve": 0.0,
    "customers_served": 0,
}

# ===== COLORS =====
CYBER_DARK = 0x0B0F1A
CYBER_CYAN = 0x1AE4FF

# ===== INTENTS =====
intents = discord.Intents.default()
intents.message_content = MESSAGE_CONTENT_INTENT

# ===== BOT INSTANCE =====
bot = commands.Bot(
    command_prefix=PREFIX,
    intents=intents,
    help_command=None
)


# ===== DATA HELPERS =====
def _ensure_file_exists():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump({}, file)


def load_data():
    _ensure_file_exists()
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}


def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def get_user_state(user_id: int) -> dict:
    data = load_data()
    state = deepcopy(DEFAULT_STATE)
    if str(user_id) in data:
        state.update(data[str(user_id)])
    else:
        data[str(user_id)] = deepcopy(state)
        save_data(data)
    return state


def update_user_state(user_id: int, state: dict):
    data = load_data()
    data[str(user_id)] = state
    save_data(data)


# ===== GAME LOGIC =====
SERVE_COOLDOWN = 10
BASE_SERVE_RANGE = (5, 15)
PC_COST = 120
CHEAP_REPAIR_COST = 45
REOPEN_COST = 40


def _working_pcs(state: dict) -> int:
    return max(0, state["pcs"] - state["broken_pcs"])


def _apply_random_event(state: dict) -> str:
    roll = random.random()
    if roll < 0.15:
        # Power surge, break a PC
        state["broken_pcs"] = min(state["pcs"], state["broken_pcs"] + 1)
        state["reputation"] = max(0, state["reputation"] - 3)
        return "⚡ Power surge fried a PC. Customers are upset."
    if roll < 0.27:
        # Police inspection closes café
        state["is_open"] = False
        state["reputation"] = max(0, state["reputation"] - 5)
        return "🚓 Surprise inspection! Café closed until you pay the fine."
    if roll < 0.35:
        bonus = random.randint(6, 14)
        state["money"] += bonus
        state["reputation"] = min(100, state["reputation"] + 2)
        return f"📣 Local streamer shouted you out! You gained ${bonus} and hype."
    return ""


def perform_serve(state: dict) -> str:
    now = time.time()
    time_since_last = now - state.get("last_serve", 0)
    if time_since_last < SERVE_COOLDOWN:
        remaining = int(SERVE_COOLDOWN - time_since_last)
        return f"Your staff is already busy. Wait {remaining}s before serving again."
    if not state["is_open"]:
        return "The Café is closed. Settle fines to reopen before serving customers."
    working = _working_pcs(state)
    if working <= 0:
        state["reputation"] = max(0, state["reputation"] - 2)
        return "No working PCs! Customers leave angry and your reputation drops."

    earnings = random.randint(*BASE_SERVE_RANGE) + max(0, working - 1)
    reputation_gain = random.choice([0, 1, 1, 2])
    state["money"] += earnings
    state["reputation"] = min(100, state["reputation"] + reputation_gain)
    state["last_serve"] = now
    state["customers_served"] += random.randint(2, 5) * working

    event_text = _apply_random_event(state)
    if not event_text:
        event_text = f"You served customers and earned ${earnings}."

    state["last_event"] = event_text
    return ""


def perform_buy_pc(state: dict) -> str:
    if state["money"] < PC_COST:
        return "Not enough cash to buy a new PC. Grind more before expanding."
    state["money"] -= PC_COST
    state["pcs"] += 1
    state["reputation"] = min(100, state["reputation"] + 1)
    state["last_event"] = "You bought a mid-range PC. More seats, more chaos."
    return ""


def perform_cheap_repair(state: dict) -> str:
    if state["broken_pcs"] <= 0:
        return "Nothing to repair. Your techs demand broken hardware first."
    if state["money"] < CHEAP_REPAIR_COST:
        return "You can't afford even the cheap parts. Earn more cash first."

    state["money"] -= CHEAP_REPAIR_COST
    if random.random() < 0.45:
        state["broken_pcs"] = min(state["pcs"], state["broken_pcs"] + 1)
        state["reputation"] = max(0, state["reputation"] - 4)
        state["last_event"] = "Cheap knockoff parts failed and broke another PC."
    else:
        state["broken_pcs"] = max(0, state["broken_pcs"] - 1)
        state["last_event"] = "Repair barely held together. One PC is limping along."
    return ""


def perform_reopen(state: dict) -> str:
    if state["is_open"]:
        return "The Café is already open. Keep serving customers."
    if state["money"] < REOPEN_COST:
        return "You can't cover the fine yet. Earn more to reopen."

    state["money"] -= REOPEN_COST
    state["is_open"] = True
    state["last_event"] = "You paid the fine and unlocked the doors again."
    return ""


# ===== UI COMPONENTS =====
def build_progress_bar(current: int, maximum: int, width: int = 12) -> str:
    filled = int((current / maximum) * width) if maximum else 0
    filled = max(0, min(width, filled))
    return "▰" * filled + "▱" * (width - filled)


def build_cafe_embed(user: discord.abc.User, state: dict) -> discord.Embed:
    working = _working_pcs(state)
    serve_ready = max(0, SERVE_COOLDOWN - int(time.time() - state.get("last_serve", 0)))
    description = (
        f"Owner: {user.mention}\n"
        f"Status: {'🟢 OPEN' if state['is_open'] else '🔴 CLOSED'}\n"
        f"Working PCs: {working}/{state['pcs']} (Broken: {state['broken_pcs']})"
    )

    embed = discord.Embed(
        title="☕ INTERNET CAFÉ CONTROL PANEL",
        description=description,
        color=CYBER_CYAN if state["is_open"] else CYBER_DARK,
    )

    embed.add_field(
        name="FINANCE",
        value=f"💵 Cash: ${state['money']}\n📈 Grind income: ${BASE_SERVE_RANGE[0]}-{BASE_SERVE_RANGE[1]} per serve",
        inline=False,
    )

    embed.add_field(
        name="REPUTATION",
        value=f"⭐ {state['reputation']}/100\n{build_progress_bar(state['reputation'], 100)}",
        inline=False,
    )

    embed.add_field(
        name="OPERATIONS",
        value=(
            f"🧑‍💻 Customers served: {state['customers_served']}\n"
            f"🕑 Serve cooldown: {'Ready' if serve_ready <= 0 else f'{serve_ready}s'}\n"
            f"⚙️ Last event: {state['last_event']}"
        ),
        inline=False,
    )

    embed.add_field(
        name="RISKS",
        value=(
            "- Power surges can break PCs\n"
            "- Cheap repairs may fail\n"
            "- Inspections can close your Café"
        ),
        inline=False,
    )

    embed.set_footer(text="CafeOS v6.6 | Chaos is expected. Grind to survive.")
    return embed


class CafeView(discord.ui.View):
    def __init__(self, owner_id: int, state: dict):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.state = state

        self.serve_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Serve Customers",
            emoji="🍜",
            custom_id=f"serve_{owner_id}"
        )
        self.serve_button.callback = self.serve

        self.buy_pc_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label=f"Buy PC (-${PC_COST})",
            emoji="🖥️",
            custom_id=f"buy_pc_{owner_id}"
        )
        self.buy_pc_button.callback = self.buy_pc

        self.repair_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label=f"Risky Repair (-${CHEAP_REPAIR_COST})",
            emoji="🛠️",
            custom_id=f"repair_{owner_id}"
        )
        self.repair_button.callback = self.repair

        self.reopen_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label=f"Reopen Café (-${REOPEN_COST})",
            emoji="🔓",
            custom_id=f"reopen_{owner_id}"
        )
        self.reopen_button.callback = self.reopen

        for button in [self.serve_button, self.buy_pc_button, self.repair_button, self.reopen_button]:
            self.add_item(button)

        self.refresh_state_buttons()

    def refresh_state_buttons(self):
        working = _working_pcs(self.state)
        serve_ready = time.time() - self.state.get("last_serve", 0) >= SERVE_COOLDOWN
        self.serve_button.disabled = not self.state["is_open"] or working <= 0 or not serve_ready
        self.buy_pc_button.disabled = self.state["money"] < PC_COST
        self.repair_button.disabled = self.state["broken_pcs"] <= 0 or self.state["money"] < CHEAP_REPAIR_COST
        self.reopen_button.disabled = self.state["is_open"] or self.state["money"] < REOPEN_COST

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This panel is locked to another Café owner.", ephemeral=True)
            return False
        return True

    async def _update_panel(self, interaction: discord.Interaction, new_state: dict):
        update_user_state(self.owner_id, new_state)
        self.state = new_state
        self.refresh_state_buttons()
        embed = build_cafe_embed(interaction.user, new_state)
        await interaction.message.edit(embed=embed, view=CafeView(self.owner_id, new_state))

    async def serve(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=False)
        state = get_user_state(self.owner_id)
        error = perform_serve(state)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        await self._update_panel(interaction, state)

    async def buy_pc(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=False)
        state = get_user_state(self.owner_id)
        error = perform_buy_pc(state)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        await self._update_panel(interaction, state)

    async def repair(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=False)
        state = get_user_state(self.owner_id)
        error = perform_cheap_repair(state)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        await self._update_panel(interaction, state)

    async def reopen(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=False)
        state = get_user_state(self.owner_id)
        error = perform_reopen(state)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        await self._update_panel(interaction, state)


def CoffeeHouseViewFactory(owner_id: int) -> CafeView:
    state = get_user_state(owner_id)
    return CafeView(owner_id, state)


# ===== EMBED BUILDERS =====
def build_help_embed():
    embed = discord.Embed(
        title="📘 INTERNET CAFÉ SIMULATOR — HELP",
        description=(
            "Run your own chaotic Café on Discord. Grind money, expand slowly, and survive the bad luck."
        ),
        color=CYBER_DARK,
    )

    embed.add_field(
        name="GETTING STARTED",
        value="☕ !cafe\nOpen your Café control panel bound to your Discord account.",
        inline=False,
    )

    embed.add_field(
        name="CORE LOOP",
        value=(
            "1) Serve customers for small cash.\n"
            "2) Save to buy more PCs.\n"
            "3) Repair breakdowns.\n"
            "4) Reopen after inspections."
        ),
        inline=False,
    )

    embed.add_field(
        name="TIPS",
        value=(
            "- Cheap repairs can backfire.\n"
            "- Closed Café earns nothing.\n"
            "- Keep some cash for fines.\n"
            "- Reputation boosts earnings."
        ),
        inline=False,
    )

    embed.set_footer(text="No cheats. No shortcuts. Earn every upgrade.")
    return embed


# ===== COMMANDS =====
@bot.command(name="cafe")
async def cafe_command(ctx: commands.Context):
    state = get_user_state(ctx.author.id)
    embed = build_cafe_embed(ctx.author, state)
    view = CoffeeHouseViewFactory(ctx.author.id)
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
if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set. Please add the bot token to the environment before starting."
    )

if not MESSAGE_CONTENT_INTENT:
    print(
        "[WARN] Message content intent disabled. Prefix commands such as !cafe and !help will not work\n"
        "Enable the Message Content Intent in your Discord developer portal and set DISCORD_MESSAGE_CONTENT_INTENT=true."
    )

try:
    bot.run(TOKEN)
except discord.errors.PrivilegedIntentsRequired as exc:
    raise RuntimeError(
        "Privileged intents are required. Enable the Message Content Intent in the Discord developer portal "
        "or set DISCORD_MESSAGE_CONTENT_INTENT=false to start without prefix commands."
    ) from exc
