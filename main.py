"""
=====================================================================
 Leo's Economy Bot - Bot Discord di economia (script unico)
=====================================================================
Tutti i comandi funzionano sia con il prefisso "." (es. .balance)
sia come slash command "/" (es. /balance): sono comandi "ibridi",
gestiti automaticamente da discord.py, non serve scriverli due volte.

AVVIO:
    1. pip install -U discord.py python-dotenv
    2. Crea un file .env nella stessa cartella con dentro:
         DISCORD_TOKEN=il_tuo_token_qui
    3. Abilita l'intent "MESSAGE CONTENT" nel portale sviluppatori Discord
       (Developer Portal -> la tua App -> Bot -> Privileged Gateway Intents)
    4. python main.py
=====================================================================
"""

import asyncio
import json
import os
import random
import threading
import time

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# =====================================================================
# CONFIGURAZIONE
# =====================================================================

PREFIX = "."
BOT_NAME = "Leo's Economy Bot"
CURRENCY_NAME = "Leo Token"
CURRENCY_EMOJI = "🪙"
EMBED_COLOR = 0xF1C40F  # oro

# ---- Cooldown (in secondi) ----
WORK_COOLDOWN = 3
LUCKY_COOLDOWN = 5 * 60  # 5 minuti
DAILY_COOLDOWN = 24 * 60 * 60
LUCKYBOX_COOLDOWN = 24 * 60 * 60
HUNT_COOLDOWN = 15
PESCA_COOLDOWN = 15
MINE_COOLDOWN = 15
COINFLIP_COOLDOWN = 3
ROULETTE_COOLDOWN = 3
BLACKJACK_COOLDOWN = 5

# ---- Work / Daily ----
WORK_MIN_REWARD = 50
WORK_MAX_REWARD = 200
DAILY_MIN_REWARD = 300
DAILY_MAX_REWARD = 600

# ---- Lucky ----
LUCKY_GAIN_PER_USE = 1
LUCKY_WIN_BONUS_PER_POINT = 0.01  # 1% per punto fortuna (max 65%)

LUCKYBOX_REWARDS = [
    {"type": "coins", "min": 50, "max": 500, "weight": 50},
    {"type": "luck", "amount": 1, "weight": 30},
    {"type": "luck", "amount": 3, "weight": 15},
    {"type": "coins", "min": 1000, "max": 5000, "weight": 5},
]

# ---- Shop - Box ----
BOXES = {
    "comune": {"label": "📦 Box Comune", "price": 100, "min": 10, "max": 100},
    "non_comune": {"label": "🟩 Box Non Comune", "price": 150, "min": 100, "max": 150},
    "rara": {"label": "🔷 Box Rara", "price": 200, "min": 200, "max": 500},
    "super_rara": {"label": "🔹 Box Super Rara", "price": 250, "min": 400, "max": 700},
    "epica": {"label": "💜 Box Epica", "price": 500, "min": 700, "max": 1000},
    "mitica": {"label": "🔥 Box Mitica", "price": 1000, "min": 1000, "max": 2000},
    "leggendaria": {"label": "👑 Box Leggendaria", "price": 2000, "min": 2500, "max": 5000},
    "ultra_leggendaria": {"label": "✨ Box Ultra Leggendaria", "price": 5000, "min": 7000, "max": 15000},
    "insane": {
        "label": "☠️ Box Insane", "price": 50000, "min": 100000, "max": 500000,
        "jackpot_chance": 0.02, "jackpot_value": 500000,
    },
}

# ---- Hunt / Pesca / Mine ----
RARITY_WEIGHTS = {"comune": 45, "non_comune": 27, "raro": 15, "epico": 8, "leggendario": 4, "mitico": 1}

ANIMALS = {
    "comune": ["coniglio", "scoiattolo", "gallina", "topo"],
    "non_comune": ["volpe", "capra", "procione", "istrice"],
    "raro": ["cervo", "lupo", "castoro", "linci"],
    "epico": ["orso", "aquila reale", "puma"],
    "leggendario": ["tigre bianca", "leone bianco"],
    "mitico": ["unicorno", "fenice"],
}
ANIMAL_VALUE_RANGES = {
    "comune": (20, 60), "non_comune": (60, 150), "raro": (150, 400),
    "epico": (400, 900), "leggendario": (900, 2000), "mitico": (2000, 5000),
}

FISH = {
    "comune": ["sardina", "acciuga", "merluzzo", "sgombro"],
    "non_comune": ["salmone", "trota", "orata"],
    "raro": ["tonno", "pesce spada"],
    "epico": ["squalo martello", "razza gigante"],
    "leggendario": ["marlin dorato", "squalo bianco"],
    "mitico": ["leviatano", "kraken"],
}
FISH_VALUE_RANGES = {
    "comune": (15, 50), "non_comune": (50, 130), "raro": (130, 350),
    "epico": (350, 800), "leggendario": (800, 1800), "mitico": (1800, 4500),
}

ORES = {
    "comune": ["carbone", "pietra", "rame"],
    "non_comune": ["ferro", "argento"],
    "raro": ["oro", "platino"],
    "epico": ["smeraldo", "zaffiro"],
    "leggendario": ["rubino", "topazio nero"],
    "mitico": ["diamante", "meteorite"],
}
ORE_VALUE_RANGES = {
    "comune": (10, 40), "non_comune": (40, 100), "raro": (100, 300),
    "epico": (300, 700), "leggendario": (700, 1600), "mitico": (1600, 4000),
}

RARITY_EMOJI = {"comune": "⚪", "non_comune": "🟢", "raro": "🔵", "epico": "🟣", "leggendario": "🟠", "mitico": "🔴"}

# ---- Giochi ----
ROULETTE_COLOR_MULTIPLIER = 2
ROULETTE_NUMBER_MULTIPLIER = 14

# ---- Admin ----
ADMIN_ROLE_IDS = []  # inserisci qui gli ID dei ruoli che possono usare add/remove

DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "economy.json")

# =====================================================================
# GESTIONE DATI (JSON)
# =====================================================================

_lock = threading.Lock()
DEFAULT_USER = {
    "wallet": 0, "bank": 0, "luck": 0, "inventory": {},
    "last_daily": 0, "last_lucky": 0, "last_luckybox": 0, "last_work": 0,
}


def _ensure_file():
    if not os.path.exists(DATA_PATH):
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load() -> dict:
    _ensure_file()
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(data: dict):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_user(user_id: int) -> dict:
    uid = str(user_id)
    with _lock:
        data = _load()
        if uid not in data:
            data[uid] = DEFAULT_USER.copy()
            data[uid]["inventory"] = {}
            _save(data)
        else:
            changed = False
            for key, val in DEFAULT_USER.items():
                if key not in data[uid]:
                    data[uid][key] = val.copy() if isinstance(val, dict) else val
                    changed = True
            if changed:
                _save(data)
        return data[uid]


def update_user(user_id: int, **fields):
    uid = str(user_id)
    with _lock:
        data = _load()
        if uid not in data:
            data[uid] = DEFAULT_USER.copy()
            data[uid]["inventory"] = {}
        data[uid].update(fields)
        _save(data)
        return data[uid]


def add_coins(user_id: int, amount: int, to: str = "wallet"):
    uid = str(user_id)
    with _lock:
        data = _load()
        if uid not in data:
            data[uid] = DEFAULT_USER.copy()
            data[uid]["inventory"] = {}
        data[uid][to] = max(0, data[uid].get(to, 0) + amount)
        _save(data)
        return data[uid][to]


def add_item(user_id: int, item_name: str, qty: int = 1):
    uid = str(user_id)
    with _lock:
        data = _load()
        if uid not in data:
            data[uid] = DEFAULT_USER.copy()
            data[uid]["inventory"] = {}
        inv = data[uid].setdefault("inventory", {})
        inv[item_name] = inv.get(item_name, 0) + qty
        _save(data)
        return inv[item_name]


def remove_item(user_id: int, item_name: str, qty: int = 1) -> bool:
    uid = str(user_id)
    with _lock:
        data = _load()
        if uid not in data:
            return False
        inv = data[uid].setdefault("inventory", {})
        if inv.get(item_name, 0) < qty:
            return False
        inv[item_name] -= qty
        if inv[item_name] <= 0:
            del inv[item_name]
        _save(data)
        return True


def now() -> int:
    return int(time.time())


# =====================================================================
# GENERAZIONE OGGETTI (hunt / pesca / mine)
# =====================================================================

def _weighted_rarity() -> str:
    rarities = list(RARITY_WEIGHTS.keys())
    weights = list(RARITY_WEIGHTS.values())
    return random.choices(rarities, weights=weights, k=1)[0]


def roll_item(category: str):
    table, value_ranges = {
        "animals": (ANIMALS, ANIMAL_VALUE_RANGES),
        "fish": (FISH, FISH_VALUE_RANGES),
        "ores": (ORES, ORE_VALUE_RANGES),
    }[category]
    rarity = _weighted_rarity()
    name = random.choice(table[rarity])
    low, high = value_ranges[rarity]
    return name, rarity, random.randint(low, high)


def find_item_info(item_name: str):
    item_name = item_name.lower().strip()
    sources = [
        ("animals", ANIMALS, ANIMAL_VALUE_RANGES),
        ("fish", FISH, FISH_VALUE_RANGES),
        ("ores", ORES, ORE_VALUE_RANGES),
    ]
    for category, table, value_ranges in sources:
        for rarity, names in table.items():
            if item_name in names:
                return category, rarity, value_ranges[rarity]
    return None


def sell_value(item_name: str) -> int:
    info = find_item_info(item_name)
    if info is None:
        return 0
    _, _, (low, high) = info
    return random.randint(low, high)


def luck_bonus(user_id: int) -> float:
    luck = get_user(user_id)["luck"]
    return min(luck * LUCKY_WIN_BONUS_PER_POINT, 0.5)


def check_bet(user_id: int, importo: int):
    if importo <= 0:
        return "❌ La puntata deve essere maggiore di 0."
    u = get_user(user_id)
    if u["wallet"] < importo:
        return "❌ Non hai abbastanza monete nel wallet."
    return None


def has_admin_role():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.guild_permissions.administrator:
            return True
        if not ADMIN_ROLE_IDS:
            return False
        user_role_ids = {r.id for r in ctx.author.roles}
        return bool(user_role_ids.intersection(ADMIN_ROLE_IDS))

    return commands.check(predicate)


# =====================================================================
# BOT SETUP
# =====================================================================

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# help_command=None: disattiva l'help predefinito, sostituito dal comando
# .help / /help personalizzato definito più sotto.
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready():
    print(f"✅ Connesso come {bot.user} (ID: {bot.user.id}) — {BOT_NAME}")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Sincronizzati {len(synced)} slash command.")
    except Exception as e:
        print(f"⚠️ Errore durante la sync degli slash command: {e}")
    print(f"{BOT_NAME} è pronto!")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        secs = round(error.retry_after, 1)
        await ctx.send(f"⏳ Rallenta! Puoi riusare questo comando tra **{secs}s**.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Ti manca un parametro: `{error.param.name}`. Controlla `.help`.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Argomento non valido. Controlla la sintassi del comando.")
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("🚫 Non hai il permesso per usare questo comando.")
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        await ctx.send(f"⚠️ Si è verificato un errore: `{error}`")
        raise error


# =====================================================================
# COMANDI ECONOMIA
# =====================================================================

@bot.hybrid_command(name="balance", aliases=["bal"], description="Mostra il tuo portafoglio e la banca.")
@app_commands.describe(utente="L'utente di cui vedere il saldo (opzionale)")
async def balance(ctx: commands.Context, utente: discord.Member = None):
    target = utente or ctx.author
    u = get_user(target.id)
    embed = discord.Embed(title=f"💰 Portafoglio di {target.display_name}", color=EMBED_COLOR)
    embed.add_field(name="Wallet", value=f"{u['wallet']} {CURRENCY_EMOJI}", inline=True)
    embed.add_field(name="Banca", value=f"{u['bank']} {CURRENCY_EMOJI}", inline=True)
    embed.add_field(name="🍀 Fortuna", value=str(u["luck"]), inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="work", description="Lavora per guadagnare qualche moneta.")
@commands.cooldown(1, WORK_COOLDOWN, commands.BucketType.user)
async def work(ctx: commands.Context):
    earned = random.randint(WORK_MIN_REWARD, WORK_MAX_REWARD)
    add_coins(ctx.author.id, earned, "wallet")
    jobs = [
        "hai consegnato dei pacchi", "hai lavorato in un bar", "hai riparato un computer",
        "hai fatto da guida turistica", "hai programmato un sito web", "hai fatto il cameriere",
    ]
    job = random.choice(jobs)
    embed = discord.Embed(
        description=f"💼 {ctx.author.mention} {job} e hai guadagnato **{earned} {CURRENCY_EMOJI}**!",
        color=EMBED_COLOR,
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="daily", description="Riscuoti la tua ricompensa giornaliera.")
async def daily(ctx: commands.Context):
    u = get_user(ctx.author.id)
    t = now()
    remaining = DAILY_COOLDOWN - (t - u["last_daily"])
    if remaining > 0:
        h, rem = divmod(remaining, 3600)
        m, s = divmod(rem, 60)
        await ctx.send(f"⏳ Hai già riscosso il daily! Riprova tra **{h}h {m}m {s}s**.")
        return
    reward = random.randint(DAILY_MIN_REWARD, DAILY_MAX_REWARD)
    add_coins(ctx.author.id, reward, "wallet")
    update_user(ctx.author.id, last_daily=t)
    embed = discord.Embed(
        description=f"🎁 {ctx.author.mention} hai riscosso la ricompensa giornaliera: **{reward} {CURRENCY_EMOJI}**!",
        color=EMBED_COLOR,
    )
    await ctx.send(embed=embed)


def _parse_amount(text: str):
    try:
        val = int(text)
        return val if val > 0 else None
    except ValueError:
        return None


@bot.hybrid_command(name="depositare", aliases=["deposit"], description="Deposita monete dal wallet alla banca.")
@app_commands.describe(importo="Quante monete depositare (o 'all' per tutte)")
async def depositare(ctx: commands.Context, importo: str):
    u = get_user(ctx.author.id)
    amount = u["wallet"] if importo.lower() in ("all", "tutto") else _parse_amount(importo)
    if amount is None or amount <= 0:
        await ctx.send("❌ Importo non valido.")
        return
    if amount > u["wallet"]:
        await ctx.send("❌ Non hai abbastanza monete nel wallet.")
        return
    add_coins(ctx.author.id, -amount, "wallet")
    add_coins(ctx.author.id, amount, "bank")
    await ctx.send(f"🏦 Hai depositato **{amount} {CURRENCY_EMOJI}** in banca.")


@bot.hybrid_command(name="prelevare", aliases=["withdraw"], description="Preleva monete dalla banca al wallet.")
@app_commands.describe(importo="Quante monete prelevare (o 'all' per tutte)")
async def prelevare(ctx: commands.Context, importo: str):
    u = get_user(ctx.author.id)
    amount = u["bank"] if importo.lower() in ("all", "tutto") else _parse_amount(importo)
    if amount is None or amount <= 0:
        await ctx.send("❌ Importo non valido.")
        return
    if amount > u["bank"]:
        await ctx.send("❌ Non hai abbastanza monete in banca.")
        return
    add_coins(ctx.author.id, -amount, "bank")
    add_coins(ctx.author.id, amount, "wallet")
    await ctx.send(f"💵 Hai prelevato **{amount} {CURRENCY_EMOJI}** dalla banca.")


@bot.hybrid_command(name="lucky", description="Aumenta la tua fortuna di 1 punto (cooldown 5 minuti).")
@commands.cooldown(1, LUCKY_COOLDOWN, commands.BucketType.user)
async def lucky(ctx: commands.Context):
    new_luck = get_user(ctx.author.id)["luck"] + LUCKY_GAIN_PER_USE
    update_user(ctx.author.id, luck=new_luck)
    await ctx.send(
        f"🍀 {ctx.author.mention} la tua fortuna è aumentata! Ora hai **{new_luck}** punti fortuna "
        f"(+{LUCKY_WIN_BONUS_PER_POINT * 100:.0f}% di vincita nei giochi per punto)."
    )


@bot.hybrid_command(name="luckybox", description="Apri la box fortunata gratuita giornaliera.")
async def luckybox(ctx: commands.Context):
    u = get_user(ctx.author.id)
    t = now()
    remaining = LUCKYBOX_COOLDOWN - (t - u["last_luckybox"])
    if remaining > 0:
        h, rem = divmod(remaining, 3600)
        m, s = divmod(rem, 60)
        await ctx.send(f"⏳ Hai già aperto la luckybox oggi! Riprova tra **{h}h {m}m {s}s**.")
        return
    weights = [r["weight"] for r in LUCKYBOX_REWARDS]
    reward = random.choices(LUCKYBOX_REWARDS, weights=weights, k=1)[0]
    update_user(ctx.author.id, last_luckybox=t)
    if reward["type"] == "coins":
        amount = random.randint(reward["min"], reward["max"])
        add_coins(ctx.author.id, amount, "wallet")
        desc = f"Hai trovato **{amount} {CURRENCY_EMOJI}**!"
    else:
        new_luck = get_user(ctx.author.id)["luck"] + reward["amount"]
        update_user(ctx.author.id, luck=new_luck)
        desc = f"Hai trovato **+{reward['amount']} punti fortuna**! (totale: {new_luck})"
    embed = discord.Embed(title="🎰 LUCKY BOX", description=f"{ctx.author.mention} {desc}", color=EMBED_COLOR)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="trade", description="Trasferisci monete a un altro utente.")
@app_commands.describe(utente="Utente a cui inviare le monete", importo="Quante monete inviare")
async def trade(ctx: commands.Context, utente: discord.Member, importo: int):
    if utente.bot:
        await ctx.send("❌ Non puoi scambiare monete con un bot.")
        return
    if utente.id == ctx.author.id:
        await ctx.send("❌ Non puoi inviare monete a te stesso.")
        return
    if importo <= 0:
        await ctx.send("❌ Importo non valido.")
        return
    sender = get_user(ctx.author.id)
    if sender["wallet"] < importo:
        await ctx.send("❌ Non hai abbastanza monete nel wallet.")
        return
    add_coins(ctx.author.id, -importo, "wallet")
    add_coins(utente.id, importo, "wallet")
    embed = discord.Embed(
        description=f"🔁 {ctx.author.mention} ha inviato **{importo} {CURRENCY_EMOJI}** a {utente.mention}!",
        color=EMBED_COLOR,
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="add", description="[ADMIN] Aggiunge monete a un utente.")
@has_admin_role()
@app_commands.describe(utente="Utente a cui aggiungere monete", importo="Quantità da aggiungere")
async def add(ctx: commands.Context, utente: discord.Member, importo: int):
    if importo <= 0:
        await ctx.send("❌ Importo non valido.")
        return
    new_balance = add_coins(utente.id, importo, "wallet")
    await ctx.send(f"✅ Aggiunti **{importo} {CURRENCY_EMOJI}** a {utente.mention}. Nuovo saldo: {new_balance}.")


@bot.hybrid_command(name="remove", description="[ADMIN] Rimuove monete da un utente.")
@has_admin_role()
@app_commands.describe(utente="Utente a cui rimuovere monete", importo="Quantità da rimuovere")
async def remove(ctx: commands.Context, utente: discord.Member, importo: int):
    if importo <= 0:
        await ctx.send("❌ Importo non valido.")
        return
    new_balance = add_coins(utente.id, -importo, "wallet")
    await ctx.send(f"✅ Rimossi **{importo} {CURRENCY_EMOJI}** da {utente.mention}. Nuovo saldo: {new_balance}.")


# =====================================================================
# SHOP
# =====================================================================

class BoxSelect(discord.ui.Select):
    def __init__(self, owner_id: int):
        self.owner_id = owner_id
        options = [
            discord.SelectOption(
                label=f"{data['label']} — {data['price']} {CURRENCY_NAME}",
                description=f"Contiene da {data['min']} a {data['max']} coins",
                value=key,
            )
            for key, data in BOXES.items()
        ]
        super().__init__(placeholder="🛒 Seleziona la Box da acquistare...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Questo shop non è tuo! Usa `.shop` per aprirne uno tuo.", ephemeral=True)
            return

        box_key = self.values[0]
        box = BOXES[box_key]
        user = get_user(interaction.user.id)

        if user["wallet"] < box["price"]:
            await interaction.response.send_message(
                f"❌ Non hai abbastanza monete! Ti servono **{box['price']} {CURRENCY_EMOJI}**.", ephemeral=True
            )
            return

        add_coins(interaction.user.id, -box["price"], "wallet")

        if "jackpot_chance" in box and random.random() < box["jackpot_chance"]:
            reward = box["jackpot_value"]
            add_coins(interaction.user.id, reward, "wallet")
            embed = discord.Embed(
                title="💥 JACKPOT!!! 💥",
                description=(
                    f"{interaction.user.mention} ha aperto **{box['label']}** e ha trovato il JACKPOT: "
                    f"**{reward} {CURRENCY_EMOJI}**!!! 🎉"
                ),
                color=0xFF0000,
            )
        else:
            reward = random.randint(box["min"], box["max"])
            add_coins(interaction.user.id, reward, "wallet")
            embed = discord.Embed(
                title="🎁 Box Aperta!",
                description=(
                    f"{interaction.user.mention} ha aperto **{box['label']}** e ha trovato "
                    f"**{reward} {CURRENCY_EMOJI}**!"
                ),
                color=EMBED_COLOR,
            )

        await interaction.response.send_message(embed=embed)


class ShopView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=120)
        self.add_item(BoxSelect(owner_id))


@bot.hybrid_command(name="shop", description="Apri lo shop delle box.")
async def shop(ctx: commands.Context):
    embed = discord.Embed(title="🛒 SHOP DEL BOT", description="Nello shop si possono comprare:\n", color=EMBED_COLOR)
    for data in BOXES.values():
        embed.description += f"\n**{data['label']}** — `{data['price']} {CURRENCY_NAME}`"
    embed.description += "\n\n✨ *Ogni Box ha una piccola probabilità di rilasciare un **BOOST ECONOMICO**!*"
    embed.description += "\n👇 *Seleziona una BOX dal menù a tendina sottostante per acquistarla!*"
    view = ShopView(ctx.author.id)
    await ctx.send(embed=embed, view=view)


# =====================================================================
# RACCOLTA: hunt / pesca / mine / inventory / sell / sellall
# =====================================================================

@bot.hybrid_command(name="hunt", description="Vai a caccia di animali.")
@commands.cooldown(1, HUNT_COOLDOWN, commands.BucketType.user)
async def hunt(ctx: commands.Context):
    name, rarity, value = roll_item("animals")
    add_item(ctx.author.id, name, 1)
    emoji = RARITY_EMOJI[rarity]
    await ctx.send(
        f"🏹 {ctx.author.mention} sei andato a caccia e hai trovato: {emoji} **{name}** "
        f"({rarity.replace('_', ' ')}) — vendibile per circa **{value} {CURRENCY_EMOJI}**!"
    )


@bot.hybrid_command(name="pesca", description="Vai a pescare pesci.")
@commands.cooldown(1, PESCA_COOLDOWN, commands.BucketType.user)
async def pesca(ctx: commands.Context):
    name, rarity, value = roll_item("fish")
    add_item(ctx.author.id, name, 1)
    emoji = RARITY_EMOJI[rarity]
    await ctx.send(
        f"🎣 {ctx.author.mention} hai pescato: {emoji} **{name}** "
        f"({rarity.replace('_', ' ')}) — vendibile per circa **{value} {CURRENCY_EMOJI}**!"
    )


@bot.hybrid_command(name="mine", description="Vai in miniera a scavare.")
@commands.cooldown(1, MINE_COOLDOWN, commands.BucketType.user)
async def mine(ctx: commands.Context):
    name, rarity, value = roll_item("ores")
    add_item(ctx.author.id, name, 1)
    emoji = RARITY_EMOJI[rarity]
    await ctx.send(
        f"⛏️ {ctx.author.mention} hai scavato e trovato: {emoji} **{name}** "
        f"({rarity.replace('_', ' ')}) — vendibile per circa **{value} {CURRENCY_EMOJI}**!"
    )


@bot.hybrid_command(name="inventory", aliases=["inv"], description="Mostra il tuo inventario.")
@app_commands.describe(utente="Utente di cui vedere l'inventario (opzionale)")
async def inventory(ctx: commands.Context, utente: discord.Member = None):
    target = utente or ctx.author
    u = get_user(target.id)
    inv = u.get("inventory", {})
    if not inv:
        await ctx.send(f"📦 L'inventario di {target.display_name} è vuoto.")
        return
    embed = discord.Embed(title=f"🎒 Inventario di {target.display_name}", color=EMBED_COLOR)
    lines = []
    for name, qty in sorted(inv.items(), key=lambda x: -x[1]):
        info = find_item_info(name)
        rarity_tag = f" ({info[1].replace('_', ' ')})" if info else ""
        lines.append(f"• **{name}**{rarity_tag} x{qty}")
    embed.description = "\n".join(lines)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="sell", description="Vendi un oggetto dal tuo inventario. Esempio: .sell coniglio")
@app_commands.describe(oggetto="Nome dell'oggetto da vendere", quantita="Quantità da vendere (default 1)")
async def sell(ctx: commands.Context, oggetto: str, quantita: int = 1):
    oggetto = oggetto.lower().strip()
    if quantita <= 0:
        await ctx.send("❌ Quantità non valida.")
        return
    u = get_user(ctx.author.id)
    owned = u.get("inventory", {}).get(oggetto, 0)
    if owned < quantita:
        await ctx.send(f"❌ Non possiedi {quantita}x **{oggetto}** (ne hai {owned}).")
        return
    total = sum(sell_value(oggetto) for _ in range(quantita))
    if total == 0:
        await ctx.send(f"❌ **{oggetto}** non è un oggetto vendibile conosciuto.")
        return
    remove_item(ctx.author.id, oggetto, quantita)
    add_coins(ctx.author.id, total, "wallet")
    await ctx.send(f"💸 {ctx.author.mention} hai venduto **{quantita}x {oggetto}** per **{total} {CURRENCY_EMOJI}**!")


@bot.hybrid_command(name="sellall", description="Vende tutto il tuo inventario.")
async def sell_all(ctx: commands.Context):
    u = get_user(ctx.author.id)
    inv = dict(u.get("inventory", {}))
    if not inv:
        await ctx.send("📦 Il tuo inventario è già vuoto.")
        return
    total = 0
    sold_items = 0
    for name, qty in inv.items():
        info = find_item_info(name)
        if info is None:
            continue
        total += sum(sell_value(name) for _ in range(qty))
        sold_items += qty
        remove_item(ctx.author.id, name, qty)
    if total == 0:
        await ctx.send("❌ Non hai oggetti vendibili nell'inventario.")
        return
    add_coins(ctx.author.id, total, "wallet")
    await ctx.send(f"💸 {ctx.author.mention} hai venduto **{sold_items}** oggetti per un totale di **{total} {CURRENCY_EMOJI}**!")


# =====================================================================
# GIOCHI: coinflip / roulette / blackjack / tris
# =====================================================================

@bot.hybrid_command(name="coinflip", aliases=["cf"], description="Lancia una moneta e scommetti.")
@commands.cooldown(1, COINFLIP_COOLDOWN, commands.BucketType.user)
@app_commands.describe(importo="Quanto scommettere", scelta="testa o croce")
@app_commands.choices(scelta=[
    app_commands.Choice(name="testa", value="testa"),
    app_commands.Choice(name="croce", value="croce"),
])
async def coinflip(ctx: commands.Context, importo: int, scelta: str):
    scelta = scelta.lower()
    if scelta not in ("testa", "croce"):
        await ctx.send("❌ Scegli tra `testa` o `croce`.")
        return
    err = check_bet(ctx.author.id, importo)
    if err:
        await ctx.send(err)
        return
    win_chance = 0.5 + luck_bonus(ctx.author.id)
    won = random.random() < win_chance
    risultato = scelta if won else ("croce" if scelta == "testa" else "testa")
    if won:
        add_coins(ctx.author.id, importo, "wallet")
        await ctx.send(f"🪙 La moneta segna **{risultato}**! Hai vinto **{importo} {CURRENCY_EMOJI}**! 🎉")
    else:
        add_coins(ctx.author.id, -importo, "wallet")
        await ctx.send(f"🪙 La moneta segna **{risultato}**! Hai perso **{importo} {CURRENCY_EMOJI}**. 😢")


@bot.hybrid_command(name="roulette", description="Gioca alla roulette: colore o numero.")
@commands.cooldown(1, ROULETTE_COOLDOWN, commands.BucketType.user)
@app_commands.describe(importo="Quanto scommettere", puntata="rosso / nero / un numero da 0 a 36")
async def roulette(ctx: commands.Context, importo: int, puntata: str):
    err = check_bet(ctx.author.id, importo)
    if err:
        await ctx.send(err)
        return
    puntata = puntata.lower().strip()
    estratto = random.randint(0, 36)
    rossi = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    colore_estratto = "verde" if estratto == 0 else ("rosso" if estratto in rossi else "nero")

    bonus = luck_bonus(ctx.author.id)
    vinto = False
    moltiplicatore = 0

    if puntata in ("rosso", "nero"):
        vinto = (puntata == colore_estratto) or (random.random() < bonus / 2)
        moltiplicatore = ROULETTE_COLOR_MULTIPLIER
    elif puntata.isdigit() and 0 <= int(puntata) <= 36:
        numero = int(puntata)
        vinto = (numero == estratto) or (random.random() < bonus / 10)
        moltiplicatore = ROULETTE_NUMBER_MULTIPLIER
    else:
        await ctx.send("❌ Puntata non valida. Usa `rosso`, `nero` oppure un numero da 0 a 36.")
        return

    embed = discord.Embed(title="🎡 Roulette", color=EMBED_COLOR)
    embed.add_field(name="Numero estratto", value=f"**{estratto}** ({colore_estratto})", inline=False)
    if vinto:
        vincita = importo * moltiplicatore
        add_coins(ctx.author.id, vincita, "wallet")
        embed.add_field(name="Risultato", value=f"🎉 Hai vinto **{vincita} {CURRENCY_EMOJI}**!", inline=False)
    else:
        add_coins(ctx.author.id, -importo, "wallet")
        embed.add_field(name="Risultato", value=f"😢 Hai perso **{importo} {CURRENCY_EMOJI}**.", inline=False)
    await ctx.send(embed=embed)


SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]


def card_value(rank: str) -> int:
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_value(hand):
    total = sum(card_value(r) for r, _ in hand)
    aces = sum(1 for r, _ in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def draw_card():
    return (random.choice(RANKS), random.choice(SUITS))


def fmt_hand(hand):
    return " ".join(f"{r}{s}" for r, s in hand)


class BlackjackGame:
    def __init__(self, user_id: int, bet: int):
        self.user_id = user_id
        self.bet = bet
        self.player = [draw_card(), draw_card()]
        self.dealer = [draw_card(), draw_card()]
        self.finished = False
        self.result_text = None

    def is_over(self):
        return hand_value(self.player) >= 21 or self.finished

    def render_embed(self, reveal_dealer=False):
        embed = discord.Embed(title="🃏 Blackjack", color=EMBED_COLOR)
        embed.add_field(name="La tua mano", value=f"{fmt_hand(self.player)} (**{hand_value(self.player)}**)", inline=False)
        if reveal_dealer or self.finished:
            embed.add_field(name="Mano del dealer", value=f"{fmt_hand(self.dealer)} (**{hand_value(self.dealer)}**)", inline=False)
        else:
            hidden = f"{self.dealer[0][0]}{self.dealer[0][1]} ❓"
            embed.add_field(name="Mano del dealer", value=hidden, inline=False)
        embed.add_field(name="Puntata", value=f"{self.bet} {CURRENCY_EMOJI}", inline=False)
        if self.result_text:
            embed.add_field(name="Risultato", value=self.result_text, inline=False)
        return embed

    async def resolve(self, message: discord.Message):
        player_total = hand_value(self.player)
        if player_total > 21:
            self.result_text = f"💥 Hai sballato con {player_total}! Perdi **{self.bet} {CURRENCY_EMOJI}**."
            add_coins(self.user_id, -self.bet, "wallet")
        else:
            while hand_value(self.dealer) < 17:
                self.dealer.append(draw_card())
            dealer_total = hand_value(self.dealer)
            if dealer_total > 21 or player_total > dealer_total:
                winnings = self.bet
                if player_total == 21 and len(self.player) == 2:
                    winnings = int(self.bet * 1.5)
                add_coins(self.user_id, winnings, "wallet")
                self.result_text = f"🎉 Hai vinto! Guadagni **{winnings} {CURRENCY_EMOJI}**."
            elif dealer_total == player_total:
                self.result_text = "🤝 Pareggio! La puntata ti viene restituita."
            else:
                add_coins(self.user_id, -self.bet, "wallet")
                self.result_text = f"😢 Il dealer vince con {dealer_total}. Perdi **{self.bet} {CURRENCY_EMOJI}**."
        self.finished = True
        await message.edit(embed=self.render_embed(reveal_dealer=True), view=None)


class BlackjackView(discord.ui.View):
    def __init__(self, game: BlackjackGame):
        super().__init__(timeout=60)
        self.game = game
        self.message: discord.Message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.game.user_id:
            await interaction.response.send_message("❌ Non è la tua partita!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Carta (Hit)", style=discord.ButtonStyle.primary, emoji="🃏")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.game.player.append(draw_card())
        if hand_value(self.game.player) >= 21:
            await interaction.response.edit_message(embed=self.game.render_embed(), view=self)
            await self.game.resolve(self.message)
            self.stop()
        else:
            await interaction.response.edit_message(embed=self.game.render_embed(), view=self)

    @discord.ui.button(label="Stai (Stand)", style=discord.ButtonStyle.success, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.game.render_embed(reveal_dealer=True), view=self)
        await self.game.resolve(self.message)
        self.stop()

    async def on_timeout(self):
        if self.message and not self.game.finished:
            self.game.result_text = "⌛ Tempo scaduto, partita annullata."
            try:
                await self.message.edit(embed=self.game.render_embed(reveal_dealer=True), view=None)
            except discord.HTTPException:
                pass


@bot.hybrid_command(name="blackjack", aliases=["bj"], description="Gioca a blackjack contro il bot.")
@commands.cooldown(1, BLACKJACK_COOLDOWN, commands.BucketType.user)
@app_commands.describe(importo="Quanto scommettere")
async def blackjack(ctx: commands.Context, importo: int):
    err = check_bet(ctx.author.id, importo)
    if err:
        await ctx.send(err)
        return
    game = BlackjackGame(ctx.author.id, importo)
    embed = game.render_embed()
    view = BlackjackView(game)
    message = await ctx.send(embed=embed, view=view)
    view.message = message
    if game.is_over():
        await game.resolve(message)


class TrisButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TrisView = self.view
        await view.handle_move(interaction, self)


class TrisView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member = None):
        super().__init__(timeout=120)
        self.player1 = player1
        self.player2 = player2
        self.current = player1
        self.board = [[None] * 3 for _ in range(3)]
        self.message: discord.Message = None
        self.game_over = False
        for y in range(3):
            for x in range(3):
                self.add_item(TrisButton(x, y))

    def winner(self):
        b = self.board
        lines = []
        lines.extend(b)
        lines.extend([[b[r][c] for r in range(3)] for c in range(3)])
        lines.append([b[i][i] for i in range(3)])
        lines.append([b[i][2 - i] for i in range(3)])
        for line in lines:
            if line[0] is not None and line[0] == line[1] == line[2]:
                return line[0]
        if all(b[r][c] is not None for r in range(3) for c in range(3)):
            return "draw"
        return None

    async def handle_move(self, interaction: discord.Interaction, button: TrisButton):
        if self.game_over:
            await interaction.response.defer()
            return
        expected_user = self.current
        if interaction.user.id != expected_user.id:
            await interaction.response.send_message("❌ Non è il tuo turno!", ephemeral=True)
            return
        if self.board[button.y][button.x] is not None:
            await interaction.response.send_message("❌ Cella già occupata!", ephemeral=True)
            return

        symbol = "❌" if self.current == self.player1 else "⭕"
        self.board[button.y][button.x] = symbol
        button.label = symbol
        button.disabled = True
        button.style = discord.ButtonStyle.danger if symbol == "❌" else discord.ButtonStyle.primary

        result = self.winner()
        if result:
            self.game_over = True
            for item in self.children:
                item.disabled = True
            if result == "draw":
                content = "🤝 Pareggio! Buona partita."
            else:
                vincitore = self.player1 if result == "❌" else (self.player2 or "Bot 🤖")
                nome = vincitore.mention if isinstance(vincitore, discord.Member) else vincitore
                content = f"🏆 Ha vinto {nome}!"
            await interaction.response.edit_message(content=content, view=self)
            self.stop()
            return

        if self.player2 is None:
            await interaction.response.edit_message(
                content=f"❌ {self.player1.mention} vs ⭕ Bot 🤖\nIl bot sta pensando...", view=self
            )
            await self._bot_move(interaction)
        else:
            self.current = self.player2 if self.current == self.player1 else self.player1
            content = f"❌ {self.player1.mention} vs ⭕ {self.player2.mention}\nTurno di: {self.current.mention}"
            await interaction.response.edit_message(content=content, view=self)

    async def _bot_move(self, interaction: discord.Interaction):
        free_cells = [item for item in self.children if isinstance(item, TrisButton) and self.board[item.y][item.x] is None]
        if not free_cells:
            return
        choice = random.choice(free_cells)
        self.board[choice.y][choice.x] = "⭕"
        choice.label = "⭕"
        choice.disabled = True
        choice.style = discord.ButtonStyle.primary

        result = self.winner()
        if result:
            self.game_over = True
            for item in self.children:
                item.disabled = True
            if result == "draw":
                content = "🤝 Pareggio! Buona partita."
            else:
                content = f"🏆 Ha vinto {'Bot 🤖' if result == '⭕' else self.player1.mention}!"
            await interaction.followup.edit_message(interaction.message.id, content=content, view=self)
            self.stop()
            return

        content = f"❌ {self.player1.mention} vs ⭕ Bot 🤖\nTurno di: {self.player1.mention}"
        await interaction.followup.edit_message(interaction.message.id, content=content, view=self)

    async def on_timeout(self):
        if self.message and not self.game_over:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(content="⌛ Tempo scaduto, partita annullata.", view=self)
            except discord.HTTPException:
                pass


@bot.hybrid_command(name="tris", description="Gioca a tris (tic-tac-toe) contro un altro utente o il bot.")
@app_commands.describe(avversario="Menziona un utente, oppure lascia vuoto per giocare contro il bot")
async def tris(ctx: commands.Context, avversario: discord.Member = None):
    if avversario and avversario.id == ctx.author.id:
        await ctx.send("❌ Non puoi giocare contro te stesso.")
        return
    if avversario and avversario.bot:
        avversario = None
    view = TrisView(ctx.author, avversario)
    content = f"❌ {ctx.author.mention} vs ⭕ {avversario.mention if avversario else 'Bot 🤖'}\nTurno di: {ctx.author.mention}"
    message = await ctx.send(content, view=view)
    view.message = message


# =====================================================================
# HELP
# =====================================================================

@bot.hybrid_command(name="help", description="Mostra tutti i comandi disponibili.")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title=f"📖 Comandi di {BOT_NAME}",
        description=f"Prefisso: `{PREFIX}` — funzionano anche come slash command `/`",
        color=EMBED_COLOR,
    )

    embed.add_field(
        name="💰 Economia",
        value=(
            f"`{PREFIX}balance [utente]` — mostra wallet, banca e fortuna\n"
            f"`{PREFIX}work` — lavora per guadagnare monete\n"
            f"`{PREFIX}daily` — ricompensa giornaliera\n"
            f"`{PREFIX}depositare <importo|all>` — deposita in banca\n"
            f"`{PREFIX}prelevare <importo|all>` — preleva dalla banca\n"
            f"`{PREFIX}trade <utente> <importo>` — invia monete a un utente"
        ),
        inline=False,
    )

    embed.add_field(
        name="🍀 Fortuna",
        value=(
            f"`{PREFIX}lucky` — +1 punto fortuna (cooldown 5 min)\n"
            f"`{PREFIX}luckybox` — box fortunata gratuita giornaliera"
        ),
        inline=False,
    )

    embed.add_field(
        name="🎒 Raccolta",
        value=(
            f"`{PREFIX}hunt` — vai a caccia\n"
            f"`{PREFIX}pesca` — vai a pescare\n"
            f"`{PREFIX}mine` — vai in miniera\n"
            f"`{PREFIX}inventory [utente]` — mostra l'inventario\n"
            f"`{PREFIX}sell <oggetto> [quantità]` — vendi un oggetto\n"
            f"`{PREFIX}sellall` — vendi tutto l'inventario"
        ),
        inline=False,
    )

    embed.add_field(
        name="🛒 Shop",
        value=f"`{PREFIX}shop` — apri lo shop delle box",
        inline=False,
    )

    embed.add_field(
        name="🎮 Giochi",
        value=(
            f"`{PREFIX}coinflip <importo> <testa|croce>` — lancia una moneta\n"
            f"`{PREFIX}roulette <importo> <rosso|nero|numero>` — roulette\n"
            f"`{PREFIX}blackjack <importo>` — blackjack contro il bot\n"
            f"`{PREFIX}tris [avversario]` — tris contro un utente o il bot"
        ),
        inline=False,
    )

    if ADMIN_ROLE_IDS or ctx.author.guild_permissions.administrator:
        embed.add_field(
            name="🛠️ Admin",
            value=(
                f"`{PREFIX}add <utente> <importo>` — aggiungi monete\n"
                f"`{PREFIX}remove <utente> <importo>` — rimuovi monete"
            ),
            inline=False,
        )

    embed.set_footer(text=f"{BOT_NAME} • Usa {PREFIX}help oppure /help")
    await ctx.send(embed=embed)


# =====================================================================
# AVVIO
# =====================================================================

if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("❌ Nessun token trovato. Crea un file .env con dentro:\nDISCORD_TOKEN=il_tuo_token_qui")
    bot.run(TOKEN)
