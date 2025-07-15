import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import os
import io
import time
import random
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from fastapi import FastAPI
import threading
import uvicorn
from discord import ui
from keep_alive import keep_alive

# --- BotとIntentsの初期化 ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- データファイルと初期化 ---
WARNING_FILE = "spam_warnings.json"
STOCK_FILE = "stock_data.json"
spam_data = {"warnings": {}, "last_reset": ""}
user_message_log = {}
backup_status = {}
auto_backup_enabled = True
CURRENCY_START = 1000
NG_WORDS = ["ばか", "うざい", "死ね"]
FUNNY_WORDS = ["草", "www", "笑った"]
NEWS_EVENTS = [
    ("政府が新政策を発表", 1.10),
    ("経済危機の兆候", 0.90),
    ("技術革新のニュース", 1.05),
    ("スキャンダル報道", 0.85),
    ("市場は安定状態", 1.00)
]

# --- スパムデータの読み書き ---
async def save_warnings():
    with open(WARNING_FILE, "w", encoding="utf-8") as f:
        json.dump(spam_data, f)

async def load_warnings():
    global spam_data
    if os.path.exists(WARNING_FILE):
        with open(WARNING_FILE, "r", encoding="utf-8") as f:
            spam_data = json.load(f)

async def reset_if_new_month():
    now = datetime.utcnow()
    current = now.strftime("%Y-%m")
    if spam_data.get("last_reset") != current:
        spam_data["warnings"] = {}
        spam_data["last_reset"] = current
        await save_warnings()

# --- 株式データの読み書き ---
def init_stock_data():
    if not os.path.exists(STOCK_FILE):
        with open(STOCK_FILE, "w") as f:
            json.dump({"users": {}, "prices": {}, "history": {}}, f)
    with open(STOCK_FILE, "r") as f:
        return json.load(f)

stock_data = init_stock_data()

def save_stock_data():
    with open(STOCK_FILE, "w") as f:
        json.dump(stock_data, f, indent=2)

def ensure_user(user_id):
    if user_id not in stock_data["users"]:
        stock_data["users"][user_id] = {"currency": CURRENCY_START, "stocks": {}, "dividend_on": True}
    if user_id not in stock_data["prices"]:
        stock_data["prices"][user_id] = 100.0
    if user_id not in stock_data["history"]:
        stock_data["history"][user_id] = []
        
# ========= INTENTS & BOT 初期化 =========
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# ========= グローバル変数 =========
spam_data = {"warnings": {}, "last_reset": ""}
user_message_log = {}
backup_status = {}
auto_backup_enabled = True
WARNING_FILE = "spam_warnings.json"
STOCK_FILE = "stock_data.json"
CURRENCY_START = 1000
NG_WORDS = ["ばか", "うざい", "死ね"]
FUNNY_WORDS = ["草", "www", "笑った"]
DIVIDEND_ENABLED = True

# ========= スパム対策 保存・読み込み =========
async def save_warnings():
    with open(WARNING_FILE, "w", encoding="utf-8") as f:
        json.dump(spam_data, f)

async def load_warnings():
    global spam_data
    if os.path.exists(WARNING_FILE):
        with open(WARNING_FILE, "r", encoding="utf-8") as f:
            spam_data = json.load(f)
    else:
        await save_warnings()

async def reset_if_new_month():
    now = datetime.utcnow()
    current = now.strftime("%Y-%m")
    if spam_data.get("last_reset") != current:
        spam_data["warnings"] = {}
        spam_data["last_reset"] = current
        await save_warnings()

# ========= 株データ保存/読み込み =========
def load_stock_data_sync():
    if not os.path.exists(STOCK_FILE):
        with open(STOCK_FILE, "w") as f:
            json.dump({"users": {}, "prices": {}, "history": {}, "names": {}}, f)
    with open(STOCK_FILE, "r") as f:
        return json.load(f)

def save_stock_data_sync():
    with open(STOCK_FILE, "w") as f:
        json.dump(stock_data, f, indent=2)

stock_data = load_stock_data_sync()

def ensure_user(uid):
    if uid not in stock_data["users"]:
        stock_data["users"][uid] = {"currency": CURRENCY_START, "stocks": {}}
    if uid not in stock_data["prices"]:
        stock_data["prices"][uid] = 100.0
    if uid not in stock_data["history"]:
        stock_data["history"][uid] = []

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# ================== データファイルと初期値 ==================
WARNING_FILE = "spam_warnings.json"
STOCK_FILE = "stock_data.json"
CURRENCY_START = 1000

spam_data = {"warnings": {}, "last_reset": ""}
user_message_log = {}
backup_status = {}
auto_backup_enabled = True

NG_WORDS = ["ばか", "うざい", "死ね"]
FUNNY_WORDS = ["草", "www", "笑った"]

# ================== 株データ初期化 ==================
if not os.path.exists(STOCK_FILE):
    with open(STOCK_FILE, "w") as f:
        json.dump({"users": {}, "prices": {}, "history": {}}, f)
with open(STOCK_FILE, "r") as f:
    stock_data = json.load(f)

# ================== 株主配当ON/OFF ==================
dividend_enabled = True

@tree.command(name="dividend_toggle", description="株主配当を有効化・無効化", guild=discord.Object(id=1276995395876028497))
async def dividend_toggle(interaction: discord.Interaction):
    global dividend_enabled
    dividend_enabled = not dividend_enabled
    msg = "✅ 配当を有効化しました" if dividend_enabled else "🛑 配当を無効化しました"
    await interaction.response.send_message(msg, ephemeral=True)

@tasks.loop(hours=1)
async def auto_dividend():
    if not dividend_enabled:
        return
    for uid in stock_data["users"]:
        stock_data["users"][uid]["stocks"][uid] = stock_data["users"][uid]["stocks"].get(uid, 0) + 0.1
    with open(STOCK_FILE, "w") as f:
        json.dump(stock_data, f, indent=2)

# ================== FastAPI ヘルスチェック ==================
app = FastAPI()

@app.get("/")
def health():
    return {"status": "alive"}

def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8080)

threading.Thread(target=run_api).start()

# ================== GUI 選択メニューサンプル ==================
class StockMenu(ui.View):
    @ui.select(
        placeholder="株関連の操作を選んでください",
        options=[
            discord.SelectOption(label="株価を見る", value="price"),
            discord.SelectOption(label="ポートフォリオ", value="portfolio"),
            discord.SelectOption(label="ランキング", value="leaderboard"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: ui.Select):
        uid = str(interaction.user.id)
        if select.values[0] == "price":
            price = stock_data["prices"].get(uid, 100.0)
            await interaction.response.send_message(f"📈 あなたの株価: {price:.2f} G", ephemeral=True)
        elif select.values[0] == "portfolio":
            user = stock_data["users"].get(uid, {"currency": CURRENCY_START, "stocks": {}})
            msg = f"💼 通貨: {user['currency']:.2f} G\n"
            for sid, count in user["stocks"].items():
                uname = (await bot.fetch_user(int(sid))).display_name
                msg += f" - {uname}: {count} 株\n"
            await interaction.response.send_message(msg, ephemeral=True)
        elif select.values[0] == "leaderboard":
            board = []
            for id_, user in stock_data["users"].items():
                total = user["currency"] + sum(stock_data["prices"].get(sid, 100.0) * cnt for sid, cnt in user["stocks"].items())
                board.append((id_, total))
            board.sort(key=lambda x: x[1], reverse=True)
            msg = "🏆 資産ランキング:\n"
            for i, (uid, total) in enumerate(board[:10], 1):
                uname = (await bot.fetch_user(int(uid))).display_name
                msg += f"{i}. {uname}: {total:.2f} G\n"
            await interaction.response.send_message(msg, ephemeral=True)

@tree.command(name="stock_menu", description="株式メニューを表示します", guild=discord.Object(id=1276995395876028497))
async def stock_menu(interaction: discord.Interaction):
    await interaction.response.send_message("📊 株式メニューはこちら！", view=StockMenu(), ephemeral=True)
    
@tree.command(name="stock_buy", description="株を購入します", guild=discord.Object(id=1276995395876028497))
@app_commands.describe(target="誰の株を買うか", amount="購入株数")
async def stock_buy(interaction: discord.Interaction, target: discord.User, amount: int):
    buyer = str(interaction.user.id)
    seller = str(target.id)
    await ensure_user(buyer)
    await ensure_user(seller)
    price = stock_data['prices'].get(seller, 100.0)
    total_cost = price * amount
    if stock_data['users'][buyer]['currency'] < total_cost:
        return await interaction.response.send_message("❌ 残高不足です。", ephemeral=True)
    stock_data['users'][buyer]['currency'] -= total_cost
    stock_data['users'][buyer]['stocks'][seller] = stock_data['users'][buyer]['stocks'].get(seller, 0) + amount
    await save_stock_data()
    await interaction.response.send_message(f"✅ {target.display_name} の株を {amount} 株 購入しました。")

@tree.command(name="stock_sell", description="株を売却します", guild=discord.Object(id=1276995395876028497))
@app_commands.describe(target="誰の株を売るか", amount="売却株数")
async def stock_sell(interaction: discord.Interaction, target: discord.User, amount: int):
    seller = str(interaction.user.id)
    target_id = str(target.id)
    await ensure_user(seller)
    owned = stock_data['users'][seller]['stocks'].get(target_id, 0)
    if owned < amount:
        return await interaction.response.send_message("❌ 所持株が足りません。", ephemeral=True)
    price = stock_data['prices'].get(target_id, 100.0)
    stock_data['users'][seller]['currency'] += price * amount
    stock_data['users'][seller]['stocks'][target_id] -= amount
    await save_stock_data()
    await interaction.response.send_message(f"💰 {target.display_name} の株を {amount} 株 売却し、{price * amount:.2f} G を得ました。")

@tree.command(name="ping", description="Botの応答速度を測定", guild=discord.Object(id=1276995395876028497))
async def ping(interaction: discord.Interaction):
    latency = bot.latency * 1000
    await interaction.response.send_message(f"🏓 Pong! 応答速度: {latency:.2f} ms")

@tree.command(name="uptime", description="Botの稼働時間を表示", guild=discord.Object(id=1276995395876028497))
async def uptime(interaction: discord.Interaction):
    uptime = datetime.utcnow() - bot.launch_time
    await interaction.response.send_message(f"🕒 稼働時間: {str(uptime).split('.')[0]}")

@tree.command(name="userinfo", description="ユーザー情報を表示", guild=discord.Object(id=1276995395876028497))
@app_commands.describe(user="調べたいユーザー")
async def userinfo(interaction: discord.Interaction, user: discord.User):
    embed = discord.Embed(title="ユーザー情報", description=f"{user.mention} の情報", color=discord.Color.blue())
    embed.add_field(name="ユーザー名", value=f"{user.name}#{user.discriminator}")
    embed.add_field(name="ID", value=user.id)
    embed.add_field(name="作成日", value=user.created_at.strftime("%Y-%m-%d %H:%M"))
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="serverinfo", description="サーバー情報を表示", guild=discord.Object(id=1276995395876028497))
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=guild.name, description="サーバー情報", color=discord.Color.green())
    embed.add_field(name="メンバー数", value=guild.member_count)
    embed.add_field(name="作成日", value=guild.created_at.strftime("%Y-%m-%d %H:%M"))
    embed.add_field(name="チャンネル数", value=len(guild.channels))
    embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
    await interaction.response.send_message(embed=embed)

# === GUI 選択メニュー対応例 ===
class StockMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="株価確認", value="price", emoji="📈"),
            discord.SelectOption(label="ポートフォリオ", value="portfolio", emoji="💼"),
            discord.SelectOption(label="ランキング", value="rank", emoji="🏆"),
        ]
        super().__init__(placeholder="操作を選んでください", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        await ensure_user(uid)
        if self.values[0] == "price":
            price = stock_data['prices'].get(uid, 100.0)
            await interaction.response.send_message(f"📈 あなたの株価: {price:.2f} G")
        elif self.values[0] == "portfolio":
            profile = stock_data["users"][uid]
            msg = f"💼 通貨: {profile['currency']:.2f} G\n"
            for sid, count in profile['stocks'].items():
                user = await bot.fetch_user(int(sid))
                price = stock_data['prices'].get(sid, 100.0)
                msg += f" - {user.display_name}: {count} 株（{price:.2f} G）\n"
            await interaction.response.send_message(msg)
        elif self.values[0] == "rank":
            board = []
            for uid_, user in stock_data["users"].items():
                total = user["currency"] + sum(stock_data['prices'].get(sid, 100.0) * count for sid, count in user['stocks'].items())
                board.append((uid_, total))
            board.sort(key=lambda x: x[1], reverse=True)
            msg = "🏆 資産ランキング:\n"
            for i, (uid_, total) in enumerate(board[:10], 1):
                name = (await bot.fetch_user(int(uid_))).display_name
                msg += f"{i}. {name}: {total:.2f} G\n"
            await interaction.response.send_message(msg)

class StockMenuView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(StockMenu())

@tree.command(name="stock_gui", description="株式管理GUIを表示", guild=discord.Object(id=1276995395876028497))
async def stock_gui(interaction: discord.Interaction):
    await interaction.response.send_message("📊 操作を選んでください：", view=StockMenuView(), ephemeral=True)

# Botの起動時間記録
bot.launch_time = datetime.utcnow()
from discord.ui import View, Select

class StockMenu(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SelectMenu())

class SelectMenu(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="株価確認", description="指定ユーザーの株価を表示"),
            discord.SelectOption(label="資産ランキング", description="全体の資産ランキング"),
            discord.SelectOption(label="ポートフォリオ", description="自分の保有株一覧")
        ]
        super().__init__(placeholder="株式メニューを選んでください", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        if self.values[0] == "株価確認":
            price = stock_data["prices"].get(uid, 100.0)
            await interaction.response.send_message(f"📈 あなたの株価は {price:.2f} G")
        elif self.values[0] == "資産ランキング":
            board = []
            for uid_, user in stock_data["users"].items():
                total = user["currency"] + sum(stock_data["prices"].get(sid, 100.0) * count for sid, count in user["stocks"].items())
                board.append((uid_, total))
            board.sort(key=lambda x: x[1], reverse=True)
            msg = "🏆 資産ランキング:\n"
            for i, (uid_, total) in enumerate(board[:10], 1):
                name = (await bot.fetch_user(int(uid_))).display_name
                msg += f"{i}. {name}: {total:.2f} G\n"
            await interaction.response.send_message(msg)
        elif self.values[0] == "ポートフォリオ":
            profile = stock_data["users"].get(uid)
            if not profile:
                await interaction.response.send_message("データが見つかりません")
                return
            msg = f"💼 通貨: {profile['currency']:.2f} G\n"
            for sid, count in profile["stocks"].items():
                user = await bot.fetch_user(int(sid))
                price = stock_data["prices"].get(sid, 100.0)
                msg += f" - {user.display_name}: {count} 株（{price:.2f} G）\n"
            await interaction.response.send_message(msg)

@tree.command(name="menu", description="株式メニューを開きます", guild=discord.Object(id=1276995395876028497))
async def menu(interaction: discord.Interaction):
    await interaction.response.send_message("📊 メニューから選択してください：", view=StockMenu(), ephemeral=True)

# ========= Bot 起動 =========
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("❌ DISCORD_BOT_TOKEN が設定されていません。")
else:
    print("🟢 Bot起動中...")
    keep_alive()
    bot.run(token)
    
@bot.event
async def on_ready():
    await load_warnings()
    await reset_if_new_month()
    await tree.sync(guild=discord.Object(id=1276995395876028497))
    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} commands.")
    except Exception as e:
        print(f"⚠️ コマンド同期エラー: {e}")
