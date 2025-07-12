import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json
import io

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# グローバルバックアップステータス（進捗管理用）
backup_status = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Sync failed: {e}")

@tree.command(name="backup", description="このチャンネルのメッセージをバックアップします")
async def backup(interaction: discord.Interaction):
    await interaction.response.send_message("📦 バックアップを開始します...", ephemeral=True)

    channel = interaction.channel
    guild_id = interaction.guild_id

    # バックアップ状態の初期化
    backup_status[guild_id] = {
        "started": True,
        "completed_channels": 0,
        "total_channels": 1,
        "messages": 0,
        "last_updated": None
    }

    messages_data = []
    async for message in channel.history(limit=None, oldest_first=True):
        messages_data.append({
            "author": str(message.author),
            "content": message.content,
            "created_at": str(message.created_at),
            "attachments": [a.url for a in message.attachments],
            "embeds": [embed.to_dict() for embed in message.embeds],
        })
        backup_status[guild_id]["messages"] += 1

    backup_status[guild_id]["completed_channels"] = 1
    backup_status[guild_id]["last_updated"] = "完了"

    # JSONに変換してファイルとして送信
    json_str = json.dumps(messages_data, indent=2, ensure_ascii=False)
    file = discord.File(fp=io.BytesIO(json_str.encode("utf-8")), filename=f"backup_{channel.id}.json")
    await interaction.followup.send("✅ バックアップが完了しました！", file=file)

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

bot.run("MTM5MzQ1NzUwNjc4ODgzOTUzNw.GTfqQX.3aH9109-F1CTSJ1oSUlJZ1WXFvIH5Wcg5CUt7E")

