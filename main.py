import io
import json
import os
import random
import time
from copy import deepcopy
from typing import Dict, Tuple

import discord
from discord.ext import commands, tasks


TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = "!"
MESSAGE_CONTENT_INTENT = os.getenv("DISCORD_MESSAGE_CONTENT_INTENT", "false").lower() == "true"

DATA_FILE = "data.json"

BASE_STATE = {
    "cash": 25,
    "pcs": 1,
    "broken_pcs": 0,
    "overheating": 1,
    "internet_level": 0,
    "electricity_level": 0,
    "customers": [],
    "staff": {"total": 0, "lazy": 0, "corrupt": 0, "skilled": 0, "technicians": 0},
    "reputation": 1.4,
    "latest_review": "The café smells like burnt circuits.",
    "alerts": {"viruses": 1, "fire": 18, "police": 6},
    "is_open": False,
    "bills": 45,
    "loan": 0,
    "open_cost": 12,
    "profit_log": [],
    "panel_message_id": None,
    "panel_channel_id": None,
    "last_tick": 0.0,
    "shop": {},
}

INTERNET_SPEEDS = ["Slow", "Stable", "Fast"]
INTERNET_COSTS = [60, 140, 260]
ELECTRICITY_COSTS = [50, 120, 220]
INCOME_PER_CUSTOMER = {"casual": (2, 4), "hardcore": (4, 7)}
CUSTOMER_DURATION = (2, 6)
HOUR_SECONDS = 10

SHOP_ITEMS = {
    "better_pc": {"name": "Refurbished PC", "cost": 130, "effect": {"pcs": 1, "overheating": 1}},
    "pro_pc": {"name": "Enthusiast PC", "cost": 320, "effect": {"pcs": 1, "overheating": 0}},
    "internet_plus": {"name": "Fiber Booster", "cost": 220, "effect": {"internet_level": 1}},
    "power_saver": {"name": "Power Optimizer", "cost": 160, "effect": {"electricity_level": 1}},
    "decor": {"name": "Comfy Decorations", "cost": 90, "effect": {"reputation": 0.2}},
    "camera": {"name": "Security Cameras", "cost": 140, "effect": {"alerts.police": -2}},
    "coffee": {"name": "Coffee Machine", "cost": 110, "effect": {"customers_stay": 1}},
}

CYBER_DARK = 0x111827
CYBER_CYAN = 0x14b8a6

intents = discord.Intents.default()
intents.message_content = MESSAGE_CONTENT_INTENT

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

panel_cache: Dict[int, discord.Message] = {}


# --------------- DATA HELPERS ---------------
def ensure_file() -> None:
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as fp:
            json.dump({}, fp)


def load_data() -> Dict[str, dict]:
    ensure_file()
    with open(DATA_FILE, "r", encoding="utf-8") as fp:
        try:
            return json.load(fp)
        except json.JSONDecodeError:
            return {}


def save_data(data: Dict[str, dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)


def get_state(user_id: int) -> dict:
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = deepcopy(BASE_STATE)
        data[str(user_id)]["last_tick"] = time.time()
        save_data(data)
    return deepcopy(data[str(user_id)])


def set_state(user_id: int, state: dict) -> None:
    data = load_data()
    data[str(user_id)] = state
    save_data(data)


# --------------- GAME HELPERS ---------------
def working_pcs(state: dict) -> int:
    return max(0, state["pcs"] - state["broken_pcs"])


def electricity_load(state: dict) -> int:
    load = 40 + (state["pcs"] * 8) - state["electricity_level"] * 6
    return max(10, min(100, load))


def internet_status(state: dict) -> str:
    return INTERNET_SPEEDS[min(len(INTERNET_SPEEDS) - 1, state["internet_level"])]


def add_profit(state: dict, amount: float) -> None:
    timestamp = time.time()
    state.setdefault("profit_log", []).append([timestamp, amount])
    state["profit_log"] = [entry for entry in state["profit_log"] if entry[0] >= timestamp - 86400]


def compute_daily_profit(state: dict) -> float:
    timestamp = time.time()
    return round(sum(amount for ts, amount in state.get("profit_log", []) if ts >= timestamp - 86400), 2)


def add_review(state: dict, text: str, delta: float) -> None:
    state["latest_review"] = text
    state["reputation"] = max(0.5, min(5.0, state["reputation"] + delta))


def spawn_customers(state: dict, count: int) -> None:
    customers = state.get("customers", [])
    for _ in range(count):
        if len(customers) >= working_pcs(state):
            break
        hardcore = random.random() < 0.25
        suspicious = random.random() < 0.15
        angry = random.random() < 0.2
        rate_range = INCOME_PER_CUSTOMER["hardcore" if hardcore else "casual"]
        base_rate = random.randint(*rate_range)
        rate = base_rate + state["internet_level"]
        duration = random.randint(*CUSTOMER_DURATION) + state["shop"].get("coffee", 0)
        customers.append(
            {
                "hardcore": hardcore,
                "suspicious": suspicious,
                "angry": angry,
                "hours_left": duration,
                "rate": rate,
            }
        )
    state["customers"] = customers


def resolve_staff(state: dict) -> Tuple[int, int]:
    technicians = state["staff"].get("technicians", 0)
    skilled = state["staff"].get("skilled", 0)
    lazy = state["staff"].get("lazy", 0)
    corrupt = state["staff"].get("corrupt", 0)

    fixes = max(0, technicians + skilled - lazy)
    mischief = max(0, corrupt - skilled)
    return fixes, mischief


def apply_hour(state: dict) -> None:
    if state["last_tick"] == 0:
        state["last_tick"] = time.time()
    pc_stress = working_pcs(state)
    fixes, mischief = resolve_staff(state)

    if state["is_open"]:
        earnings = 0
        remaining_customers = []
        for customer in state.get("customers", []):
            earnings += customer["rate"]
            customer["hours_left"] -= 1
            if customer["hours_left"] > 0:
                remaining_customers.append(customer)
            else:
                if customer["angry"]:
                    add_review(state, "They never cleaned the PCs.", -0.1)
                elif customer["hardcore"]:
                    add_review(state, "Decent rigs for marathon gaming.", 0.05)
        state["customers"] = remaining_customers
        state["cash"] += earnings
        add_profit(state, earnings)
        state["daily_profit"] = compute_daily_profit(state)
    else:
        state["customers"] = []

    if state["customers"] and random.random() < 0.25:
        state["overheating"] = min(state["pcs"], state["overheating"] + 1)

    if pc_stress <= 0 or random.random() < 0.12 + max(0, state["overheating"] - fixes) * 0.02:
        if state["broken_pcs"] < state["pcs"]:
            state["broken_pcs"] += 1
            add_review(state, "Another station died mid-match.", -0.15)

    state["broken_pcs"] = min(state["pcs"], max(0, state["broken_pcs"] - fixes))
    if fixes > 0:
        state["overheating"] = max(0, state["overheating"] - fixes)

    if mischief > 0:
        loss = mischief * 6
        state["cash"] = max(0, state["cash"] - loss)
        state["alerts"]["police"] = min(20, state["alerts"].get("police", 0) + mischief)
        add_review(state, "Rumors of bribery float around.", -0.05)

    state["bills"] += max(3, electricity_load(state) // 6)
    salary_cost = state["staff"]["total"] * 2
    state["bills"] += salary_cost

    if state["bills"] > state["cash"] + 80:
        state["is_open"] = False
        state["latest_review"] = "Bills piled up. Doors locked until you pay."

    if random.random() < 0.18:
        state["alerts"]["viruses"] = min(10, state["alerts"]["viruses"] + 1)
    if state["alerts"]["viruses"] >= 7 and random.random() < 0.25:
        state["broken_pcs"] = min(state["pcs"], state["broken_pcs"] + 1)

    fire_risk = electricity_load(state) + state["overheating"] * 4
    state["alerts"]["fire"] = min(100, max(5, fire_risk))
    state["alerts"]["police"] = max(0, min(100, state["alerts"].get("police", 0)))

    state["last_tick"] += HOUR_SECONDS


def tick_state(user_id: str, state: dict, hours: int) -> dict:
    for _ in range(hours):
        apply_hour(state)
    return state


# --------------- EMBEDS ---------------
def format_customers(state: dict) -> Tuple[int, int, int, int]:
    active = len(state.get("customers", []))
    angry = sum(1 for c in state.get("customers", []) if c.get("angry"))
    hardcore = sum(1 for c in state.get("customers", []) if c.get("hardcore"))
    suspicious = sum(1 for c in state.get("customers", []) if c.get("suspicious"))
    return active, angry, hardcore, suspicious


def build_panel_embed(user: discord.abc.User, state: dict) -> discord.Embed:
    active, angry, hardcore, suspicious = format_customers(state)
    embed = discord.Embed(
        title="☕ INTERNET CAFE CONTROL PANEL",
        description=(
            f"Owner: {user.mention}\n"
            f"Status: {'🟢 OPEN' if state['is_open'] else '🔴 CLOSED'} | Reputation: {state['reputation']:.1f}/5"
        ),
        color=CYBER_CYAN if state["is_open"] else CYBER_DARK,
    )

    embed.add_field(
        name="SYSTEM STATUS",
        value=(
            f"💻 PCs: {state['pcs']}\n"
            f"🔥 Overheating: {state['overheating']}\n"
            f"❌ Broken: {state['broken_pcs']}\n\n"
            f"🌐 Internet Speed: {internet_status(state)}\n"
            f"⚡ Electricity Load: {electricity_load(state)}%"
        ),
        inline=False,
    )

    embed.add_field(
        name="CUSTOMERS",
        value=(
            f"🧍 Active: {active}\n"
            f"😡 Angry: {angry}\n"
            f"🎮 Hardcore Gamers: {hardcore}\n"
            f"🕵️ Suspicious Users: {suspicious}"
        ),
        inline=False,
    )

    embed.add_field(
        name="STAFF",
        value=(
            f"👨‍💼 Total Staff: {state['staff']['total']}\n"
            f"😴 Lazy: {state['staff']['lazy']}\n"
            f"💰 Corrupt: {state['staff']['corrupt']}\n"
            f"🧠 Skilled: {state['staff']['skilled']}"
        ),
        inline=False,
    )

    embed.add_field(
        name="FINANCE",
        value=(
            f"💵 Cash: ${round(state['cash'], 2)}\n"
            f"📈 Daily Profit: +${compute_daily_profit(state)}\n"
            f"📉 Bills: -${round(state['bills'], 2)}"
        ),
        inline=False,
    )

    embed.add_field(
        name="REPUTATION",
        value=(
            f"⭐ Rating: {state['reputation']:.1f}/5\n"
            f"📝 Latest Review:\n" f"\"{state['latest_review']}\""
        ),
        inline=False,
    )

    embed.add_field(
        name="ALERTS",
        value=(
            f"⚠️ Active Viruses: {state['alerts']['viruses']}\n"
            f"🔥 Fire Risk Level: {state['alerts']['fire']}\n"
            f"🚓 Police Attention Level: {state['alerts']['police']}"
        ),
        inline=False,
    )

    embed.set_footer(text="Numbers shift every 10 seconds. Grind, react, survive.")
    return embed


# --------------- VIEW ---------------
class CafeView(discord.ui.View):
    def __init__(self, owner_id: int, state: dict):
        super().__init__(timeout=None)
        self.owner_id = owner_id
        self.state = state
        self.build_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This control panel is bound to another user.", ephemeral=True)
            return False
        return True

    def build_buttons(self) -> None:
        self.clear_items()
        self.add_item(discord.ui.Button(label="SYSTEM", style=discord.ButtonStyle.gray, disabled=True))
        self.add_item(self._button("Buy PC", "buy_pc", discord.ButtonStyle.success))
        self.add_item(self._button("Repair PC", "repair_pc", discord.ButtonStyle.secondary))
        self.add_item(self._button("Upgrade Internet", "upgrade_internet", discord.ButtonStyle.primary))
        self.add_item(self._button("Upgrade Electricity", "upgrade_electric", discord.ButtonStyle.primary))

        self.add_item(discord.ui.Button(label="CUSTOMERS", style=discord.ButtonStyle.gray, disabled=True))
        self.add_item(self._button("Accept Customers", "accept_customers", discord.ButtonStyle.success))
        self.add_item(self._button("Kick Angry Customer", "kick_angry", discord.ButtonStyle.danger))
        self.add_item(self._button("Ban Suspicious User", "ban_suspicious", discord.ButtonStyle.danger))

        self.add_item(discord.ui.Button(label="STAFF", style=discord.ButtonStyle.gray, disabled=True))
        self.add_item(self._button("Hire Staff", "hire_staff", discord.ButtonStyle.success))
        self.add_item(self._button("Fire Staff", "fire_staff", discord.ButtonStyle.secondary))
        self.add_item(self._button("Assign Technician", "assign_tech", discord.ButtonStyle.primary))
        self.add_item(self._button("Bribe Corrupt Staff", "bribe_staff", discord.ButtonStyle.danger))

        self.add_item(discord.ui.Button(label="FINANCE", style=discord.ButtonStyle.gray, disabled=True))
        self.add_item(self._button("Open Cafe", "open_cafe", discord.ButtonStyle.success))
        self.add_item(self._button("Close Cafe", "close_cafe", discord.ButtonStyle.secondary))
        self.add_item(self._button("Pay Bills", "pay_bills", discord.ButtonStyle.primary))
        self.add_item(self._button("Take Loan", "take_loan", discord.ButtonStyle.danger))

        self.add_item(discord.ui.Button(label="REPUTATION", style=discord.ButtonStyle.gray, disabled=True))
        self.add_item(self._button("Clean Cafe", "clean_cafe", discord.ButtonStyle.success))
        self.add_item(self._button("Improve Service", "improve_service", discord.ButtonStyle.primary))
        self.add_item(self._button("Fake Review (illegal)", "fake_review", discord.ButtonStyle.danger))
        self.refresh_disabled()

    def _button(self, label: str, action: str, style: discord.ButtonStyle) -> discord.ui.Button:
        button = discord.ui.Button(label=label, style=style, custom_id=f"{action}_{self.owner_id}")
        button.callback = getattr(self, action)
        return button

    def refresh_disabled(self) -> None:
        state = self.state
        cost_pc = 95 + state["pcs"] * 30
        cost_internet = INTERNET_COSTS[state["internet_level"]] if state["internet_level"] < len(INTERNET_COSTS) else 9999
        cost_electric = ELECTRICITY_COSTS[state["electricity_level"]] if state["electricity_level"] < len(ELECTRICITY_COSTS) else 9999
        active, angry, hardcore, suspicious = format_customers(state)

        for item in self.children:
            if not isinstance(item, discord.ui.Button) or item.disabled:
                continue
            if item.custom_id.startswith("buy_pc"):
                item.disabled = state["cash"] < cost_pc
            elif item.custom_id.startswith("repair_pc"):
                item.disabled = state["broken_pcs"] <= 0 or state["cash"] < 40
            elif item.custom_id.startswith("upgrade_internet"):
                item.disabled = state["internet_level"] >= len(INTERNET_COSTS) - 1 or state["cash"] < cost_internet
            elif item.custom_id.startswith("upgrade_electric"):
                item.disabled = state["electricity_level"] >= len(ELECTRICITY_COSTS) - 1 or state["cash"] < cost_electric
            elif item.custom_id.startswith("accept_customers"):
                item.disabled = not state["is_open"] or working_pcs(state) <= 0
            elif item.custom_id.startswith("kick_angry"):
                item.disabled = angry <= 0
            elif item.custom_id.startswith("ban_suspicious"):
                item.disabled = suspicious <= 0
            elif item.custom_id.startswith("hire_staff"):
                item.disabled = state["cash"] < 55
            elif item.custom_id.startswith("fire_staff"):
                item.disabled = state["staff"]["total"] <= 0
            elif item.custom_id.startswith("assign_tech"):
                item.disabled = state["staff"]["skilled"] <= 0
            elif item.custom_id.startswith("bribe_staff"):
                item.disabled = state["staff"]["corrupt"] <= 0 or state["cash"] < 30
            elif item.custom_id.startswith("open_cafe"):
                item.disabled = state["is_open"] or state["cash"] < state["open_cost"]
            elif item.custom_id.startswith("close_cafe"):
                item.disabled = not state["is_open"]
            elif item.custom_id.startswith("pay_bills"):
                item.disabled = state["bills"] <= 0 or state["cash"] < state["bills"]
            elif item.custom_id.startswith("take_loan"):
                item.disabled = state["loan"] > 0
            elif item.custom_id.startswith("clean_cafe"):
                item.disabled = state["cash"] < 20
            elif item.custom_id.startswith("improve_service"):
                item.disabled = state["cash"] < 60
            elif item.custom_id.startswith("fake_review"):
                item.disabled = state["cash"] < 35

    async def _update(self, interaction: discord.Interaction, state: dict) -> None:
        set_state(self.owner_id, state)
        embed = build_panel_embed(interaction.user, state)
        await interaction.response.edit_message(embed=embed, view=CafeView(self.owner_id, state))

    async def buy_pc(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        cost = 95 + state["pcs"] * 30
        if state["cash"] < cost:
            await interaction.response.send_message("You can't afford another junk PC yet.", ephemeral=True)
            return
        state["cash"] -= cost
        state["pcs"] += 1
        state["overheating"] += 1
        add_review(state, "More seats, same dusty floor.", 0)
        await self._update(interaction, state)

    async def repair_pc(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["broken_pcs"] <= 0:
            await interaction.response.send_message("No broken rigs to fix.", ephemeral=True)
            return
        cost = 40
        if state["cash"] < cost:
            await interaction.response.send_message("Too broke for duct tape repairs.", ephemeral=True)
            return
        state["cash"] -= cost
        if random.random() < 0.4:
            state["broken_pcs"] = min(state["pcs"], state["broken_pcs"] + 1)
            add_review(state, "Repair scam ruined another station.", -0.2)
        else:
            state["broken_pcs"] = max(0, state["broken_pcs"] - 1)
        await self._update(interaction, state)

    async def upgrade_internet(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["internet_level"] >= len(INTERNET_COSTS) - 1:
            await interaction.response.send_message("Connection is already maxed.", ephemeral=True)
            return
        cost = INTERNET_COSTS[state["internet_level"]]
        if state["cash"] < cost:
            await interaction.response.send_message("Save up for a better ISP plan.", ephemeral=True)
            return
        state["cash"] -= cost
        state["internet_level"] += 1
        add_review(state, "Ping finally feels playable.", 0.1)
        await self._update(interaction, state)

    async def upgrade_electric(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["electricity_level"] >= len(ELECTRICITY_COSTS) - 1:
            await interaction.response.send_message("Power grid already stable enough.", ephemeral=True)
            return
        cost = ELECTRICITY_COSTS[state["electricity_level"]]
        if state["cash"] < cost:
            await interaction.response.send_message("Can't pay the electrician yet.", ephemeral=True)
            return
        state["cash"] -= cost
        state["electricity_level"] += 1
        state["overheating"] = max(0, state["overheating"] - 1)
        await self._update(interaction, state)

    async def accept_customers(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if not state["is_open"]:
            await interaction.response.send_message("Open the cafe before inviting anyone.", ephemeral=True)
            return
        spawn_customers(state, random.randint(1, 3))
        await self._update(interaction, state)

    async def kick_angry(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        customers = state.get("customers", [])
        angry = [c for c in customers if c.get("angry")]
        if not angry:
            await interaction.response.send_message("No angry customers to kick.", ephemeral=True)
            return
        target = angry[0]
        customers.remove(target)
        state["customers"] = customers
        add_review(state, "Bouncer removed a screamer.", 0.05)
        await self._update(interaction, state)

    async def ban_suspicious(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        customers = state.get("customers", [])
        suspects = [c for c in customers if c.get("suspicious")]
        if not suspects:
            await interaction.response.send_message("No suspicious activity detected.", ephemeral=True)
            return
        target = suspects[0]
        customers.remove(target)
        state["customers"] = customers
        state["alerts"]["police"] = max(0, state["alerts"]["police"] - 3)
        await self._update(interaction, state)

    async def hire_staff(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        cost = 55
        if state["cash"] < cost:
            await interaction.response.send_message("Can't afford new hires.", ephemeral=True)
            return
        state["cash"] -= cost
        state["staff"]["total"] += 1
        roll = random.random()
        if roll < 0.4:
            state["staff"]["lazy"] += 1
        elif roll < 0.65:
            state["staff"]["corrupt"] += 1
        else:
            state["staff"]["skilled"] += 1
        await self._update(interaction, state)

    async def fire_staff(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["staff"]["total"] <= 0:
            await interaction.response.send_message("No staff to fire.", ephemeral=True)
            return
        state["staff"]["total"] -= 1
        for key in ("lazy", "corrupt", "skilled", "technicians"):
            if state["staff"].get(key, 0) > 0:
                state["staff"][key] -= 1
                break
        await self._update(interaction, state)

    async def assign_tech(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["staff"]["skilled"] <= 0:
            await interaction.response.send_message("No skilled worker to assign.", ephemeral=True)
            return
        state["staff"]["skilled"] -= 1
        state["staff"]["technicians"] += 1
        add_review(state, "A tech now patrols the rigs.", 0.05)
        await self._update(interaction, state)

    async def bribe_staff(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["staff"]["corrupt"] <= 0:
            await interaction.response.send_message("No corrupt staff to bribe.", ephemeral=True)
            return
        cost = 30
        if state["cash"] < cost:
            await interaction.response.send_message("You can't cover the hush money.", ephemeral=True)
            return
        state["cash"] -= cost
        state["alerts"]["police"] = max(0, state["alerts"]["police"] - 4)
        add_review(state, "Rumors quieted down for now.", 0)
        await self._update(interaction, state)

    async def open_cafe(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["is_open"]:
            await interaction.response.send_message("Already open for business.", ephemeral=True)
            return
        if state["cash"] < state["open_cost"]:
            await interaction.response.send_message("Can't afford to unlock the doors.", ephemeral=True)
            return
        state["cash"] -= state["open_cost"]
        state["is_open"] = True
        add_review(state, "Doors creak open again.", 0)
        set_state(self.owner_id, state)
        await interaction.response.edit_message(embed=build_panel_embed(interaction.user, state), view=CafeView(self.owner_id, state))

    async def close_cafe(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if not state["is_open"]:
            await interaction.response.send_message("Already closed.", ephemeral=True)
            return
        state["is_open"] = False
        state["customers"] = []
        await self._update(interaction, state)

    async def pay_bills(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["bills"] <= 0:
            await interaction.response.send_message("No bills pending.", ephemeral=True)
            return
        if state["cash"] < state["bills"]:
            await interaction.response.send_message("Not enough cash to settle debts.", ephemeral=True)
            return
        state["cash"] -= state["bills"]
        state["bills"] = 0
        state["is_open"] = True
        add_review(state, "Suppliers got paid. Doors stay open.", 0.1)
        await self._update(interaction, state)

    async def take_loan(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        if state["loan"] > 0:
            await interaction.response.send_message("Repay your current loan first.", ephemeral=True)
            return
        amount = 120
        state["cash"] += amount
        state["loan"] = amount * 1.25
        state["alerts"]["police"] = min(100, state["alerts"]["police"] + 5)
        await self._update(interaction, state)

    async def clean_cafe(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        cost = 20
        if state["cash"] < cost:
            await interaction.response.send_message("Too broke to buy cleaning supplies.", ephemeral=True)
            return
        state["cash"] -= cost
        add_review(state, "Floors finally got mopped.", 0.15)
        await self._update(interaction, state)

    async def improve_service(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        cost = 60
        if state["cash"] < cost:
            await interaction.response.send_message("Can't afford training right now.", ephemeral=True)
            return
        state["cash"] -= cost
        add_review(state, "Staff learned to reboot routers politely.", 0.25)
        spawn_customers(state, 1)
        await self._update(interaction, state)

    async def fake_review(self, interaction: discord.Interaction):
        state = get_state(self.owner_id)
        cost = 35
        if state["cash"] < cost:
            await interaction.response.send_message("Can't pay for bots yet.", ephemeral=True)
            return
        state["cash"] -= cost
        add_review(state, "Suspiciously glowing online praise.", 0.35)
        state["alerts"]["police"] = min(100, state["alerts"]["police"] + 10)
        await self._update(interaction, state)


# --------------- SHOP ---------------
class ShopView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=60)
        self.owner_id = owner_id
        options = [
            discord.SelectOption(label=item["name"], description=f"${item['cost']}", value=key)
            for key, item in SHOP_ITEMS.items()
        ]
        self.select = discord.ui.Select(placeholder="Buy an upgrade", min_values=1, max_values=1, options=options)
        self.select.callback = self.purchase
        self.add_item(self.select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Not your shopping cart.", ephemeral=True)
            return False
        return True

    async def purchase(self, interaction: discord.Interaction):
        choice = self.select.values[0]
        item = SHOP_ITEMS[choice]
        state = get_state(self.owner_id)
        if state["cash"] < item["cost"]:
            await interaction.response.send_message("Too expensive right now.", ephemeral=True)
            return
        state["cash"] -= item["cost"]
        state["shop"][choice] = state["shop"].get(choice, 0) + 1
        for key, value in item["effect"].items():
            if key == "internet_level":
                state["internet_level"] = min(len(INTERNET_SPEEDS) - 1, state["internet_level"] + value)
            elif key == "electricity_level":
                state["electricity_level"] = min(len(ELECTRICITY_COSTS) - 1, state["electricity_level"] + value)
            elif key == "pcs":
                state["pcs"] += value
            elif key == "overheating":
                state["overheating"] = max(0, state["overheating"] - abs(value) if value < 0 else state["overheating"] + value)
            elif key == "reputation":
                add_review(state, state["latest_review"], value)
            elif key == "alerts.police":
                state["alerts"]["police"] = max(0, state["alerts"]["police"] + value)
            elif key == "customers_stay":
                state.setdefault("shop", {})
        set_state(self.owner_id, state)
        await interaction.response.send_message(
            f"Purchased {item['name']}!", ephemeral=True
        )


# --------------- COMMANDS ---------------
@bot.command(name="cafe")
async def cafe(ctx: commands.Context):
    state = get_state(ctx.author.id)
    embed = build_panel_embed(ctx.author, state)
    view = CafeView(ctx.author.id, state)
    message = None
    if state.get("panel_message_id"):
        channel = bot.get_channel(state["panel_channel_id"])
        try:
            message = await channel.fetch_message(state["panel_message_id"])
            await message.edit(embed=embed, view=view)
        except Exception:
            message = None
    if message is None:
        message = await ctx.send(embed=embed, view=view)
        state["panel_message_id"] = message.id
        state["panel_channel_id"] = message.channel.id
        set_state(ctx.author.id, state)
    panel_cache[ctx.author.id] = message


@bot.command(name="help")
async def help_cmd(ctx: commands.Context):
    embed = discord.Embed(
        title="📘 INTERNET CAFE SIMULATOR HELP",
        description=(
            "Grind from a single dusty PC to a chaotic empire. Keep the panel open with !cafe and react to crises."
        ),
        color=CYBER_DARK,
    )
    embed.add_field(
        name="Core Loop",
        value="Accept customers, survive events, pay bills, and upgrade slowly. The panel updates itself every 10 seconds.",
        inline=False,
    )
    embed.add_field(
        name="Shop",
        value="Use !shop to buy upgrades like better PCs, internet, electricity optimizers, and ambience items.",
        inline=False,
    )
    embed.set_footer(text="Progress is slow. Decisions matter.")
    await ctx.send(embed=embed)


@bot.command(name="shop")
async def shop_cmd(ctx: commands.Context):
    view = ShopView(ctx.author.id)
    await ctx.send("Select an item to purchase:", view=view)


@bot.command(name="data")
async def data_cmd(ctx: commands.Context):
    state = get_state(ctx.author.id)
    payload = json.dumps(state, indent=2)
    buffer = io.BytesIO(payload.encode("utf-8"))
    await ctx.send(file=discord.File(buffer, filename="data.json"))


# --------------- BACKGROUND LOOP ---------------
@tasks.loop(seconds=HOUR_SECONDS)
async def hourly_tick():
    data = load_data()
    now = time.time()
    changed = False
    for user_id, state in data.items():
        elapsed = int((now - state.get("last_tick", now)) // HOUR_SECONDS)
        if elapsed <= 0:
            continue
        changed = True
        state = tick_state(user_id, state, elapsed)
        data[user_id] = state
        if state.get("panel_message_id") and state.get("panel_channel_id"):
            channel = bot.get_channel(state["panel_channel_id"])
            if channel:
                try:
                    message = panel_cache.get(int(user_id)) or await channel.fetch_message(state["panel_message_id"])
                    panel_cache[int(user_id)] = message
                    user = bot.get_user(int(user_id)) or (message.author if hasattr(message, "author") else bot.user)
                    embed = build_panel_embed(user, state)
                    await message.edit(embed=embed, view=CafeView(int(user_id), state))
                except Exception:
                    panel_cache.pop(int(user_id), None)
    if changed:
        save_data(data)


@hourly_tick.before_loop
async def before_tick():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    print("===================================")
    print(f"Logged in as: {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("Internet Cafe Simulator booted")
    print("===================================")
    if not hourly_tick.is_running():
        hourly_tick.start()


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set. Please add the bot token to the environment before starting.")

if not MESSAGE_CONTENT_INTENT:
    print(
        "[WARN] Message content intent disabled. Prefix commands such as !cafe and !help will not work.\n"
        "Enable the Message Content Intent in your Discord developer portal and set DISCORD_MESSAGE_CONTENT_INTENT=true."
    )

try:
    bot.run(TOKEN)
except discord.errors.PrivilegedIntentsRequired as exc:
    raise RuntimeError(
        "Privileged intents are required. Enable the Message Content Intent in the Discord developer portal "
        "or set DISCORD_MESSAGE_CONTENT_INTENT=false to start without prefix commands."
    ) from exc
