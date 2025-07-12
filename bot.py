import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import io
from datetime import datetime, timedelta
import os
import time

# =====================
# ゲーム定義
# =====================
EMPTY = "🟩"  # 空きマス: 緑
BLACK = "⚫"
WHITE = "⚪"

class OthelloGame:
    def __init__(self, player1, player2):
        self.board = [[EMPTY for _ in range(8)] for _ in range(8)]
        self.board[3][3] = WHITE
        self.board[3][4] = BLACK
        self.board[4][3] = BLACK
        self.board[4][4] = WHITE
        self.players = [player1, player2]
        self.current_turn = 0

    def display_board(self):
        return '\n'.join(' '.join(row) for row in self.board)

    def in_bounds(self, x, y):
        return 0 <= x < 8 and 0 <= y < 8

    def current_player(self):
        return self.players[self.current_turn % 2]

    def current_color(self):
        return BLACK if self.current_turn % 2 == 0 else WHITE

    def make_move(self, x, y):
        if not self.in_bounds(x, y) or self.board[y][x] != EMPTY:
            return False

        color = self.current_color()
        opponent = WHITE if color == BLACK else BLACK
        directions = [(-1, -1), (-1, 0), (-1, 1),
                      (0, -1),         (0, 1),
                      (1, -1), (1, 0), (1, 1)]
        flipped = []

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            temp = []
            while self.in_bounds(nx, ny) and self.board[ny][nx] == opponent:
                temp.append((nx, ny))
                nx += dx
                ny += dy
            if self.in_bounds(nx, ny) and self.board[ny][nx] == color and temp:
                flipped.extend(temp)

        if not flipped:
            return False

        self.board[y][x] = color
        for nx, ny in flipped:
            self.board[ny][nx] = color
        self.current_turn += 1
        return True

    def count_pieces(self):
        black = sum(row.count(BLACK) for row in self.board)
        white = sum(row.count(WHITE) for row in self.board)
        return black, white

# =====================
# Discord Bot 設定
# =====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

games = {}  # channel_id: OthelloGame

@tree.command(name="othello_start", description="オセロを開始します")
@app_commands.describe(opponent="対戦相手")
async def othello_start(interaction: discord.Interaction, opponent: discord.User):
    if interaction.channel_id in games:
        await interaction.response.send_message("⚠️ このチャンネルではすでにオセロが行われています。", ephemeral=True)
        return

    game = OthelloGame(interaction.user, opponent)
    games[interaction.channel_id] = game

    await interaction.response.send_message(embed=create_board_embed(game, "🟢 オセロ開始！", f"{interaction.user.mention}（⚫） vs {opponent.mention}（⚪）"))

@tree.command(name="othello_move", description="指定位置に石を置きます")
@app_commands.describe(x="X座標 (0-7)", y="Y座標 (0-7)")
async def othello_move(interaction: discord.Interaction, x: int, y: int):
    game = games.get(interaction.channel_id)
    if not game:
        await interaction.response.send_message("❌ このチャンネルではオセロが開始されていません。", ephemeral=True)
        return

    if interaction.user != game.current_player():
        await interaction.response.send_message("❌ あなたの番ではありません。", ephemeral=True)
        return

    if not game.make_move(x, y):
        await interaction.response.send_message("❌ 無効な手です。", ephemeral=True)
        return

    await interaction.response.send_message(embed=create_board_embed(game, f"{interaction.user.name} が ({x}, {y}) に石を置きました！"))

@tree.command(name="othello_end", description="現在のオセロゲームを終了します")
async def othello_end(interaction: discord.Interaction):
    if interaction.channel_id in games:
        del games[interaction.channel_id]
        await interaction.response.send_message("🛑 オセロゲームを終了しました。")
    else:
        await interaction.response.send_message("⚠️ 終了するオセロゲームがありません。", ephemeral=True)

def create_board_embed(game: OthelloGame, title: str, description: str = "") -> discord.Embed:
    black_count, white_count = game.count_pieces()
    embed = discord.Embed(title=title, description=description, color=discord.Color.green())
    embed.add_field(name="盤面", value=f"```\n{game.display_board()}```", inline=False)
    embed.add_field(name="石の数", value=f"⚫: {black_count}　⚪: {white_count}", inline=False)
    embed.set_footer(text=f"{game.current_player().name}（{game.current_color()}）の番です")
    return embed
  

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # ← 🔥 これがないと @tree.command は使えません！

@tree.command(name="ping", description="Botの応答速度を確認します")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {bot.user}")


# =====================
# Bot 初期設定
# =====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# =====================
# スパム対策関係
# =====================
user_message_log = {}  # ユーザーのメッセージ履歴 {user_id: [msg1, msg2, ...]}
spam_data = {"warnings": {}, "last_reset": ""}
WARNING_FILE = "spam_warnings.json"

# -----------------
# 保存・読み込み処理
# -----------------
def save_warnings():
    with open(WARNING_FILE, "w", encoding="utf-8") as f:
        json.dump(spam_data, f)

def load_warnings():
    global spam_data
    if os.path.exists(WARNING_FILE):
        with open(WARNING_FILE, "r", encoding="utf-8") as f:
            spam_data = json.load(f)
    else:
        save_warnings()

# -----------------
# 月ごとのリセット
# -----------------
def reset_if_new_month():
    now = datetime.utcnow()
    current = now.strftime("%Y-%m")
    if spam_data.get("last_reset") != current:
        spam_data["warnings"] = {}
        spam_data["last_reset"] = current
        save_warnings()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    now = time.time()

    log = user_message_log.setdefault(user_id, [])
    log.append((message.content, now))
    log[:] = [(content, t) for content, t in log if now - t <= 5]

    counts = {}
    for content, t in log:
        counts[content] = counts.get(content, 0) + 1

    for count in counts.values():
        if count >= 5:
            warnings = spam_data["warnings"].get(user_id, 0) + 1
            spam_data["warnings"][user_id] = warnings
            save_warnings()

            if warnings >= 5:
                timeout_duration = 3600  # 1時間
            else:
                timeout_duration = 600  # 10分

            try:
                await message.author.timeout(discord.utils.utcnow() + timedelta(seconds=timeout_duration))
                await message.channel.send(
                    f"🚨 {message.author.mention} はスパム検出によりタイムアウトされました。警告回数: {warnings} 回\n"
                    f"🚨 {message.author.mention} has been timed out for spamming. Warning count: {warnings} times"
                )
            except Exception as e:
                print("タイムアウト失敗:", e)
            break

    await bot.process_commands(message)

# =====================
# スラッシュコマンド
# =====================

@tree.command(name="warns", description="特定ユーザーのスパム警告数を表示します")
@app_commands.describe(user="警告数を確認したいユーザー")
async def warns(interaction: discord.Interaction, user: discord.User):
    load_warnings()
    user_id = str(user.id)
    warn_count = spam_data["warnings"].get(user_id, 0)
    return interaction.response.send_message(
        f"🛡️ {user.mention} の警告回数: {warn_count} 回\n"
        f"🛡️ Warning count for {user.mention}: {warn_count} times",
        ephemeral=True
    )

@tree.command(name="resetwarns", description="特定ユーザーのスパム警告数をリセットします（管理者専用）")
@app_commands.describe(user="警告をリセットする対象ユーザー")
async def resetwarns(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ 管理者権限が必要です。\n❌ Administrator permission required.", ephemeral=True)

    user_id = str(user.id)
    spam_data["warnings"].pop(user_id, None)
    save_warnings()

    await interaction.response.send_message(
        f"♻️ {user.mention} の警告数をリセットしました。\n"
        f"♻️ Reset warning count for {user.mention}.", ephemeral=True
    )

@tree.command(name="help", description="このBotの機能一覧を表示します")
async def help_command(interaction: discord.Interaction):
    await interaction.response.send_message(
        """**📘 Botコマンド一覧 / Command List:**
・/backup [days] - メッセージをバックアップ
・/restore [file] - メッセージ復元
・/status - バックアップ進捗確認
・/warns [user] - スパム警告数確認
・/resetwarns [user] - スパム警告リセット（管理者）
・/help - この一覧を表示

💡 スパム対策は自動で動作します（5秒以内に同じ発言を5回で警告＋タイムアウト）
""",
        ephemeral=True
    )

# =====================
# バックアップ機能
# =====================
backup_status = {}

@tree.command(name="backup", description="このチャンネルのメッセージをバックアップします")
@app_commands.describe(days="バックアップ対象とする過去の日数")
async def backup(interaction: discord.Interaction, days: int = 7):
    await interaction.response.send_message(f"📦 過去 {days} 日分のバックアップを開始します...", ephemeral=True)
    channel = interaction.channel
    guild_id = interaction.guild_id

    backup_status[guild_id] = {
        "started": True,
        "completed_channels": 0,
        "total_channels": 1,
        "messages": 0,
        "last_updated": None
    }

    messages_data = []
    after_time = datetime.utcnow() - timedelta(days=days)

    async for message in channel.history(limit=None, oldest_first=True, after=after_time):
        messages_data.append({
            "display_name": message.author.display_name,
            "avatar_url": message.author.display_avatar.url,
            "content": message.content,
            "created_at": str(message.created_at),
            "attachments": [a.url for a in message.attachments],
            "embeds": [embed.to_dict() for embed in message.embeds],
        })
        backup_status[guild_id]["messages"] += 1

    backup_status[guild_id]["completed_channels"] = 1
    backup_status[guild_id]["last_updated"] = "完了"

    json_str = json.dumps(messages_data, indent=2, ensure_ascii=False)
    file = discord.File(fp=io.BytesIO(json_str.encode("utf-8")), filename=f"backup_{channel.id}_last_{days}_days.json")
    await interaction.followup.send(f"✅ 過去 {days} 日分のバックアップが完了しました！", file=file)

@tree.command(name="status", description="現在のバックアップ状況を確認します")
async def status(interaction: discord.Interaction):
    guild_id = interaction.guild_id
    status = backup_status.get(guild_id)

    if not status or not status.get("started"):
        await interaction.response.send_message("❌ 現在進行中のバックアップはありません。", ephemeral=True)
        return

    progress = (
        f"📝 チャンネル: {status['completed_channels']} / {status['total_channels']}\n"
        f"💬 メッセージ数: {status['messages']}\n"
        f"📅 最終更新: {status['last_updated']}"
    )
    await interaction.response.send_message(f"📊 バックアップ進行状況:\n{progress}", ephemeral=True)

@tree.command(name="restore", description="バックアップファイルからメッセージを復元します")
@app_commands.describe(file="バックアップJSONファイルを添付してください")
async def restore(interaction: discord.Interaction, file: discord.Attachment):
    if not file.filename.endswith(".json"):
        await interaction.response.send_message("❌ 有効なJSONファイルをアップロードしてください。", ephemeral=True)
        return

    await interaction.response.send_message("🔄 復元を開始します...", ephemeral=True)

    try:
        content = await file.read()
        messages_data = json.loads(content.decode("utf-8"))
    except Exception as e:
        await interaction.followup.send(f"❌ 復元ファイルの読み込みに失敗しました: {e}", ephemeral=True)
        return

    try:
        webhook = await interaction.channel.create_webhook(name="復元Bot")
    except discord.Forbidden:
        await interaction.followup.send("❌ Webhookを作成できません。BotにWebhookの権限があるか確認してください。", ephemeral=True)
        return

    async def send_message_via_webhook(msg):
        display_name = msg.get("display_name", "Unknown")
        avatar_url = msg.get("avatar_url", None)
        content = msg.get("content", "")
        embeds = [discord.Embed.from_dict(e) for e in msg.get("embeds", [])]

        try:
            await webhook.send(
                content=content if content else None,
                username=display_name,
                avatar_url=avatar_url,
                embeds=embeds,
                wait=True
            )
        except Exception as e:
            print(f"送信失敗: {e}")

    tasks = [send_message_via_webhook(msg) for msg in messages_data]
    await asyncio.gather(*tasks)

    try:
        await webhook.delete()
    except Exception as e:
        print(f"Webhook削除失敗: {e}")

    await interaction.followup.send(f"✅ 復元が完了しました！ ({len(messages_data)} 件)", ephemeral=True)

# =====================
# 起動処理
# =====================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}!")
    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"⚠️ Sync failed: {e}")

# 起動（環境変数からトークン取得）
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("❌ DISCORD_BOT_TOKEN が設定されていません。")
else:
    bot.run(token)

