import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import json
import io
import time
import os
from datetime import datetime, timedelta

# --- 初期設定 ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.guild_messages = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# データストア
queue = []
loop_song = False
disconnect_timer = {}
user_message_log = {}
spam_data = {"warnings": {}, "last_reset": ""}
WARNING_FILE = "spam_warnings.json"
backup_status = {}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
}
YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "extract_flat": False
}

# --- ユーティリティ関数 ---
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

def reset_if_new_month():
    now = datetime.utcnow()
    current = now.strftime("%Y-%m")
    if spam_data.get("last_reset") != current:
        spam_data["warnings"] = {}
        spam_data["last_reset"] = current
        save_warnings()

def get_source(url):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "url": info["url"],
            "title": info.get("title"),
            "webpage_url": info.get("webpage_url")
        }

async def play_next(vc, interaction):
    global queue, loop_song
    if loop_song and queue:
        song = queue[0]
    elif queue:
        song = queue.pop(0)
    else:
        return

    source = await discord.FFmpegOpusAudio.from_probe(song["url"], **FFMPEG_OPTIONS)
    vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(vc, interaction), bot.loop))

    embed = discord.Embed(
        title="🎵 Now Playing",
        description=f"[{song['title']}]({song['webpage_url']})",
        color=0x1DB954
    )
    await interaction.followup.send(embed=embed)

async def auto_disconnect(vc):
    if vc.is_connected():
        await vc.disconnect()
        print(f"⏰ 自動切断: {vc.guild.name}")

# --- イベント処理 ---
@bot.event
async def on_ready():
    load_warnings()
    reset_if_new_month()
    try:
        sync_count = await tree.sync()
        print(f"✅ Synced {len(sync_count)} slash commands")
    except Exception as e:
        print(f"⚠️ Sync failed: {e}")
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    load_warnings()
    reset_if_new_month()
    uid = str(message.author.id)
    now = time.time()
    log = user_message_log.setdefault(uid, [])
    log.append((message.content, now))
    log[:] = [(c, t) for c, t in log if now - t <= 5]

    counts = {}
    for c, t in log:
        counts[c] = counts.get(c, 0) + 1

    for cnt in counts.values():
        if cnt >= 5:
            warn = spam_data["warnings"].get(uid, 0) + 1
            spam_data["warnings"][uid] = warn
            save_warnings()
            dur = 3600 if warn >= 5 else 600
            try:
                await message.author.timeout(discord.utils.utcnow() + timedelta(seconds=dur))
                await message.channel.send(f"🚨 {message.author.mention} はスパムです。警告: {warn}回")
            except Exception as e:
                print("タイムアウトエラー:", e)
            break

    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    vc = discord.utils.get(bot.voice_clients, guild=member.guild)
    if not vc:
        return
    if len(vc.channel.members) == 1:
        if member.guild.id in disconnect_timer:
            disconnect_timer[member.guild.id].cancel()
        disconnect_timer[member.guild.id] = bot.loop.call_later(
            600, lambda: asyncio.create_task(auto_disconnect(vc))
        )

# --- スラッシュコマンド ---
@tree.command(name="ping", description="応答速度を確認します")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!", ephemeral=True)

@tree.command(name="warns", description="特定ユーザーの警告数を表示")
@app_commands.describe(user="対象ユーザー")
async def warns(interaction: discord.Interaction, user: discord.User):
    load_warnings()
    warn = spam_data["warnings"].get(str(user.id), 0)
    await interaction.response.send_message(f"{user.mention} の警告数: {warn} 回", ephemeral=True)

@tree.command(name="resetwarns", description="警告数リセット（管理者限定）")
@app_commands.describe(user="対象ユーザー")
async def resetwarns(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ 管理者権限が必要です", ephemeral=True)
    spam_data["warnings"].pop(str(user.id), None)
    save_warnings()
    await interaction.response.send_message(f"{user.mention} の警告をリセットしました", ephemeral=True)

@tree.command(name="play", description="YouTube音源を再生")
@app_commands.describe(url="YouTubeのURL")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    voice = interaction.user.voice
    if not voice:
        return await interaction.followup.send("❌ 先にVCに入ってください")
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    try:
        src = get_source(url)
    except Exception as e:
        return await interaction.followup.send(f"❌ 再生に失敗しました: {e}")
    if vc and vc.is_connected():
        queue.append(src)
        await interaction.followup.send(f"✅ キューに追加: [{src['title']}]({src['webpage_url']})")
    else:
        vc = await voice.channel.connect()
        queue.append(src)
        await play_next(vc, interaction)

@tree.command(name="stop", description="再生を停止")
async def stop(interaction: discord.Interaction):
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏹️ 再生停止")
    else:
        await interaction.response.send_message("❌ 再生中ではありません")

@tree.command(name="leave", description="VCから退出")
async def leave(interaction: discord.Interaction):
    vc = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if vc:
        await vc.disconnect()
        await interaction.response.send_message("👋 VCから退出しました")
    else:
        await interaction.response.send_message("❌ 接続されていません")

@tree.command(name="loop", description="ループモード切替")
async def loop_cmd(interaction: discord.Interaction):
    global loop_song
    loop_song = not loop_song
    await interaction.response.send_message(f"🔁 ループ: {'有効' if loop_song else '無効'}")

@tree.command(name="backup", description="メッセージをバックアップ")
@app_commands.describe(days="過去何日分か")
async def backup(interaction: discord.Interaction, days: int = 7):
    await interaction.response.send_message(f"📦 過去 {days} 日のメッセージをバックアップ中…", ephemeral=True)
    ch = interaction.channel; gid = interaction.guild_id
    backup_status[gid] = {"started": True, "completed_channels": 0, "total_channels": 1, "messages": 0, "last_updated": None}
    arr = []; after = datetime.utcnow() - timedelta(days=days)
    async for msg in ch.history(limit=None, oldest_first=True, after=after):
        arr.append({"display_name": msg.author.display_name, "avatar_url": msg.author.display_avatar.url, "content": msg.content,
                    "created_at": str(msg.created_at), "attachments": [a.url for a in msg.attachments],
                    "embeds": [e.to_dict() for e in msg.embeds]})
        backup_status[gid]["messages"] += 1
    backup_status[gid].update({"completed_channels": 1, "last_updated": "完了"})
    stream = io.BytesIO(json.dumps(arr, ensure_ascii=False, indent=2).encode("utf-8"))
    await interaction.followup.send(f"✅ 完了: {backup_status[gid]['messages']} 件", file=discord.File(stream, filename=f"backup_{ch.id}_{days}d.json"))

@tree.command(name="restore", description="メッセージを復元")
@app_commands.describe(file="バックアップJSONファイル")
async def restore(interaction: discord.Interaction, file: discord.Attachment):
    if not file.filename.endswith(".json"):
        return await interaction.response.send_message("❌ JSONファイルをアップロードしてください", ephemeral=True)
    await interaction.response.send_message("🔄 復元中…", ephemeral=True)
    try:
        data = json.loads((await file.read()).decode("utf-8"))
    except Exception as e:
        return await interaction.followup.send(f"❌ 読み込み失敗: {e}", ephemeral=True)
    try:
        webhook = await interaction.channel.create_webhook(name="復元Bot")
    except discord.Forbidden:
        return await interaction.followup.send("❌ Webhook作成権限がありません", ephemeral=True)
    async def send(msg):
        await webhook.send(content=msg.get("content") or None, username=msg.get("display_name"), avatar_url=msg.get("avatar_url"),
                            embeds=[discord.Embed.from_dict(e) for e in msg.get("embeds", [])], wait=True)
    await asyncio.gather(*(send(m) for m in data))
    await webhook.delete()
    await interaction.followup.send(f"✅ 復元完了: {len(data)} 件", ephemeral=True)

@tree.command(name="status", description="バックアップ状況を確認")
async def status(interaction: discord.Interaction):
    st = backup_status.get(interaction.guild_id)
    if not st or not st.get("started"):
        return await interaction.response.send_message("❌ バックアップ中の処理はありません", ephemeral=True)
    txt = f"📝 チャンネル: {st['completed_channels']} / {st['total_channels']}\n💬 メッセージ数: {st['messages']}\n📅 最終更新: {st['last_updated']}"
    await interaction.response.send_message(txt, ephemeral=True)

@tree.command(name="help", description="機能一覧を表示")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(
        """**📘 Botコマンド一覧:**
/ping - 応答確認  
/warns [user] - スパム警告数確認  
/resetwarns [user] - 警告リセット (管理者のみ)  
/backup [days] - メッセージをバックアップ  
/restore [file] - メッセージ復元  
/status - バックアップ進捗確認  
/backupserver - サーバー設定をバックアップ  
/play [YouTube URL] - 音源を再生  
/stop - 音楽停止  
/leave - VCを離脱  
/loop - ループ再生切替  
/help - この一覧を表示""",
        ephemeral=True
    )

@tree.command(name="backupserver", description="サーバー・チャンネル・ロール設定をバックアップ")
async def backupserver(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    data = {
        "server": {
            "name": guild.name,
            "icon_url": guild.icon.url if guild.icon else None,
            "afk_channel": guild.afk_channel.name if guild.afk_channel else None,
            "afk_timeout": guild.afk_timeout
        },
        "roles": [
            {"id": r.id, "name": r.name, "color": r.color.value, "permissions": r.permissions.value, 
             "position": r.position, "hoist": r.hoist, "mentionable": r.mentionable}
            for r in guild.roles
        ],
        "channels": [
            {"id": c.id, "name": c.name, "type": str(c.type), "category": c.category.name if c.category else None,
             "topic": getattr(c, "topic", None), "nsfw": getattr(c, "is_nsfw", False)}
            for c in guild.channels
        ]
    }
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    await interaction.followup.send("📦 サーバー設定バックアップ", file=discord.File(buf, filename=f"server_{guild.id}_settings.json"), ephemeral=True)

# --- 起動 ---
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("❌ DISCORD_BOT_TOKEN を環境変数に設定してください")
else:
    print("🟢 Botを起動します…")
    bot.run(token)
