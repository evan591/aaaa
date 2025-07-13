import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
import io
import asyncio
import time
from datetime import datetime, timedelta

# ========= INTENTS & BOT 初期化 =========
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
tree = bot.tree

# ========= グローバル変数 =========
spam_data = {"warnings": {}, "last_reset": ""}
user_message_log = {}
backup_status = {}
auto_backup_enabled = True
WARNING_FILE = "spam_warnings.json"

# ========= スパム対策（保存・読み込み） =========
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

# ========= スパム検出 =========
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    now = time.time()
    log = user_message_log.setdefault(user_id, [])
    log.append((message.content, now))
    log[:] = [(c, t) for c, t in log if now - t <= 5]

    counts = {}
    for content, t in log:
        counts[content] = counts.get(content, 0) + 1

    for count in counts.values():
        if count >= 5:
            warnings = spam_data["warnings"].get(user_id, 0) + 1
            spam_data["warnings"][user_id] = warnings
            save_warnings()

            timeout_duration = 3600 if warnings >= 5 else 600
            try:
                await message.author.timeout(discord.utils.utcnow() + timedelta(seconds=timeout_duration))
                await message.channel.send(
                    f"🚨 {message.author.mention} タイムアウトされました。警告: {warnings} 回"
                )
            except Exception as e:
                print(f"タイムアウト失敗: {e}")
            break

    await bot.process_commands(message)

# ========= スパムコマンド =========
@tree.command(name="warns", description="スパム警告数確認")
@app_commands.describe(user="対象ユーザー")
async def warns(interaction: discord.Interaction, user: discord.User):
    load_warnings()
    warn_count = spam_data["warnings"].get(str(user.id), 0)
    await interaction.response.send_message(f"{user.mention} の警告数: {warn_count}", ephemeral=True)

@tree.command(name="resetwarns", description="警告数をリセット（管理者）")
@app_commands.describe(user="対象ユーザー")
async def resetwarns(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("管理者専用コマンドです。", ephemeral=True)
    spam_data["warnings"].pop(str(user.id), None)
    save_warnings()
    await interaction.response.send_message(f"{user.mention} の警告数をリセットしました。", ephemeral=True)

# ========= バックアップ & 復元 =========
@tree.command(name="backup", description="メッセージをバックアップ")
@app_commands.describe(days="過去何日分を保存するか")
async def backup(interaction: discord.Interaction, days: int = 7):
    await interaction.response.send_message(f"📦 過去 {days} 日のメッセージを保存中...", ephemeral=True)
    channel = interaction.channel
    guild_id = interaction.guild_id
    after_time = datetime.utcnow() - timedelta(days=days)

    messages_data = []
    async for message in channel.history(limit=None, oldest_first=True, after=after_time):
        messages_data.append({
            "display_name": message.author.display_name,
            "avatar_url": message.author.display_avatar.url,
            "content": message.content,
            "created_at": str(message.created_at),
            "attachments": [a.url for a in message.attachments],
            "embeds": [embed.to_dict() for embed in message.embeds],
        })

    backup_status[guild_id] = {
        "started": True,
        "completed_channels": 1,
        "total_channels": 1,
        "messages": len(messages_data),
        "last_updated": str(datetime.utcnow())
    }

    json_str = json.dumps(messages_data, ensure_ascii=False, indent=2)
    file = discord.File(io.BytesIO(json_str.encode("utf-8")), filename=f"backup_{channel.id}.json")
    await interaction.followup.send("✅ バックアップ完了！", file=file)

@tree.command(name="status", description="バックアップ状況を確認")
async def status(interaction: discord.Interaction):
    s = backup_status.get(interaction.guild_id)
    if not s:
        return await interaction.response.send_message("現在バックアップは行われていません。", ephemeral=True)
    await interaction.response.send_message(
        f"📊 チャンネル: {s['completed_channels']}/{s['total_channels']}\n"
        f"💬 メッセージ: {s['messages']}\n"
        f"🕒 更新: {s['last_updated']}", ephemeral=True
    )

@tree.command(name="restore", description="バックアップを復元（Webhook使用）")
@app_commands.describe(file="バックアップファイル（.json）")
async def restore(interaction: discord.Interaction, file: discord.Attachment):
    if not file.filename.endswith(".json"):
        return await interaction.response.send_message("JSONファイルをアップロードしてください。", ephemeral=True)

    await interaction.response.send_message("復元を開始中...", ephemeral=True)
    try:
        content = await file.read()
        messages = json.loads(content.decode("utf-8"))
    except Exception as e:
        return await interaction.followup.send(f"読み込み失敗: {e}", ephemeral=True)

    try:
        webhook = await interaction.channel.create_webhook(name="復元Webhook")
    except discord.Forbidden:
        return await interaction.followup.send("Webhook作成に失敗しました。", ephemeral=True)

    async def send_message(msg):
        try:
            await webhook.send(
                content=msg["content"] or None,
                username=msg["display_name"],
                avatar_url=msg["avatar_url"],
                embeds=[discord.Embed.from_dict(e) for e in msg.get("embeds", [])],
                wait=True
            )
        except Exception as e:
            print(f"送信失敗: {e}")

    await asyncio.gather(*(send_message(m) for m in messages))
    await webhook.delete()
    await interaction.followup.send(f"✅ 復元完了！({len(messages)} 件)", ephemeral=True)

# ========= テンプレート機能 =========
@tree.command(name="save_template", description="ロール・チャンネル構成を保存")
async def save_template(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("管理者専用", ephemeral=True)

    guild = interaction.guild
    data = {"roles": [], "categories": [], "channels": []}

    for role in guild.roles:
        if role.is_default(): continue
        data["roles"].append({
            "name": role.name,
            "permissions": role.permissions.value,
            "color": role.color.value,
            "hoist": role.hoist,
            "mentionable": role.mentionable,
        })

    for category in guild.categories:
        data["categories"].append({"name": category.name, "position": category.position})

    for channel in guild.channels:
        ch_data = {
            "type": "text" if isinstance(channel, discord.TextChannel) else "voice",
            "name": channel.name,
            "category": channel.category.name if channel.category else None,
            "position": channel.position
        }
        data["channels"].append(ch_data)

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    file = discord.File(io.BytesIO(json_str.encode("utf-8")), filename=f"{guild.name}_template.json")
    await interaction.response.send_message("✅ テンプレート保存完了", file=file, ephemeral=True)

@tree.command(name="load_template", description="テンプレートから復元")
@app_commands.describe(file="テンプレートファイル（.json）")
async def load_template(interaction: discord.Interaction, file: discord.Attachment):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("管理者専用", ephemeral=True)

    await interaction.response.send_message("復元中...", ephemeral=True)

    try:
        template = json.loads((await file.read()).decode("utf-8"))
    except Exception as e:
        return await interaction.followup.send(f"読み込み失敗: {e}", ephemeral=True)

    guild = interaction.guild
    category_map = {}

    for r in template["roles"]:
        try:
            await guild.create_role(
                name=r["name"],
                permissions=discord.Permissions(r["permissions"]),
                color=discord.Color(r["color"]),
                hoist=r["hoist"],
                mentionable=r["mentionable"]
            )
        except Exception as e:
            print(f"ロール作成失敗: {e}")

    for c in sorted(template["categories"], key=lambda x: x["position"]):
        try:
            obj = await guild.create_category(c["name"])
            category_map[c["name"]] = obj
        except Exception as e:
            print(f"カテゴリ作成失敗: {e}")

    for ch in template["channels"]:
        try:
            cat = category_map.get(ch["category"]) if ch["category"] else None
            if ch["type"] == "text":
                await guild.create_text_channel(name=ch["name"], category=cat)
            else:
                await guild.create_voice_channel(name=ch["name"], category=cat)
        except Exception as e:
            print(f"チャンネル作成失敗: {e}")

    await interaction.followup.send("✅ サーバー構成復元完了", ephemeral=True)

# ========= 自動バックアップタスク =========
@tasks.loop(hours=168)
async def weekly_backup_task():
    print("🔄 自動バックアップ実行（タスク内容は実装してください）")

# ========= on_ready =========
@bot.event
async def on_ready():
    reset_if_new_month()
    load_warnings()
    try:
        await tree.sync()
        print(f"✅ Synced {len(await tree.sync())} commands")
    except Exception as e:
        print(f"⚠️ Sync failed: {e}")
    if auto_backup_enabled and not weekly_backup_task.is_running():
        weekly_backup_task.start()
        print("▶️ 自動バックアップ開始")

# ========= 自動バックアップ ON/OFF =========
@tree.command(name="backup_on", description="自動バックアップを有効化")
async def backup_on(interaction: discord.Interaction):
    global auto_backup_enabled
    auto_backup_enabled = True
    if not weekly_backup_task.is_running():
        weekly_backup_task.start()
    await interaction.response.send_message("✅ 自動バックアップを有効化", ephemeral=True)

@tree.command(name="backup_off", description="自動バックアップを無効化")
async def backup_off(interaction: discord.Interaction):
    global auto_backup_enabled
    auto_backup_enabled = False
    if weekly_backup_task.is_running():
        weekly_backup_task.cancel()
    await interaction.response.send_message("🛑 自動バックアップを無効化", ephemeral=True)

# ========= Bot 起動 =========
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("❌ DISCORD_BOT_TOKEN が設定されていません。")
else:
    print("🟢 Bot起動中...")
    bot.run(token)
