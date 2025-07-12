import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import json
import io
from datetime import datetime, timedelta
import os
import time


# オセロ盤面サイズ
BOARD_SIZE = 8

# 初期化
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# 石の定義
EMPTY = "🟩"
BLACK = "⚫"
WHITE = "⚪"

# 方向（8方向）
DIRECTIONS = [(-1, -1), (-1, 0), (-1, 1),
              (0, -1),         (0, 1),
              (1, -1),  (1, 0), (1, 1)]

class OthelloGame:
    def __init__(self, player1: discord.User, player2: discord.User):
        self.board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.board[3][3] = WHITE
        self.board[3][4] = BLACK
        self.board[4][3] = BLACK
        self.board[4][4] = WHITE
        self.players = [player1, player2]
        self.turn = 0  # 0: player1 (black), 1: player2 (white)
        self.finished = False

    def current_player(self):
        return self.players[self.turn]

    def current_color(self):
        return BLACK if self.turn == 0 else WHITE

    def display_board(self):
        board_str = "　" + "".join(f"{i}" for i in range(BOARD_SIZE)) + "\n"
        for i, row in enumerate(self.board):
            board_str += f"{i} " + "".join(row) + "\n"
        return board_str

    def is_valid_move(self, x, y):
        if self.board[y][x] != EMPTY:
            return False

        current = self.current_color()
        opponent = BLACK if current == WHITE else WHITE

        for dx, dy in DIRECTIONS:
            nx, ny = x + dx, y + dy
            found_opponent = False

            while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if self.board[ny][nx] == opponent:
                    found_opponent = True
                    nx += dx
                    ny += dy
                elif self.board[ny][nx] == current and found_opponent:
                    return True
                else:
                    break
        return False

    def place_stone(self, x, y):
        if not self.is_valid_move(x, y):
            return False

        current = self.current_color()
        opponent = BLACK if current == WHITE else WHITE

        self.board[y][x] = current
        for dx, dy in DIRECTIONS:
            nx, ny = x + dx, y + dy
            path = []

            while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                if self.board[ny][nx] == opponent:
                    path.append((nx, ny))
                    nx += dx
                    ny += dy
                elif self.board[ny][nx] == current:
                    for px, py in path:
                        self.board[py][px] = current
                    break
                else:
                    break

        self.turn = 1 - self.turn
        return True

    def count_pieces(self):
        black = sum(row.count(BLACK) for row in self.board)
        white = sum(row.count(WHITE) for row in self.board)
        return black, white


games = {}  # guild_id -> OthelloGame

@tree.command(name="othello_start", description="オセロを開始します")
@app_commands.describe(opponent="対戦相手")
async def start_game(interaction: discord.Interaction, opponent: discord.User):
    if interaction.guild_id in games:
        await interaction.response.send_message("既にゲームが進行中です。", ephemeral=True)
        return

    if opponent == interaction.user:
        await interaction.response.send_message("自分とは対戦できません。", ephemeral=True)
        return

    games[interaction.guild_id] = OthelloGame(interaction.user, opponent)
    game = games[interaction.guild_id]
    await interaction.response.send_message(
        f"🟢 オセロ開始！\n"
        f"{interaction.user.mention}（⚫） vs {opponent.mention}（⚪）\n\n"
        f"現在の盤面:\n```{game.display_board()}```\n"
        f"{game.current_player().mention} の番です（{game.current_color()}）"
    )

@tree.command(name="othello_move", description="石を置きます（例: /othello_move x:2 y:3）")
@app_commands.describe(x="横（0〜7）", y="縦（0〜7）")
async def move(interaction: discord.Interaction, x: int, y: int):
    game = games.get(interaction.guild_id)
    if not game:
        await interaction.response.send_message("ゲームが開始されていません。", ephemeral=True)
        return

    if interaction.user != game.current_player():
        await interaction.response.send_message("今はあなたの番ではありません。", ephemeral=True)
        return

    if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
        await interaction.response.send_message("無効な座標です。", ephemeral=True)
        return

    if not game.place_stone(x, y):
        await interaction.response.send_message("その位置には置けません。", ephemeral=True)
        return

    black_count, white_count = game.count_pieces()

    await interaction.response.send_message(
        f"✅ {interaction.user.mention} が ({x}, {y}) に石を置きました！\n"
        f"```{game.display_board()}```\n"
        f"⚫: {black_count}　⚪: {white_count}\n"
        f"次は {game.current_player().mention} の番です（{game.current_color()}）"
    )

@tree.command(name="othello_end", description="現在のオセロゲームを終了します")
async def end_game(interaction: discord.Interaction):
    if interaction.guild_id not in games:
        await interaction.response.send_message("終了するゲームはありません。", ephemeral=True)
        return

    del games[interaction.guild_id]
    await interaction.response.send_message("ゲームを終了しました。")

@bot.event
async def on_ready():
    await tree.sync()
    print(f"ログイン完了: {bot.user}")



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

