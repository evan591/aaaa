import os
import json
import time
import asyncio
from discord.ext import commands
from discord import app_commands, Intents, Interaction
from dotenv import load_dotenv

backup_status = {}

load_dotenv()
TOKEN = os.getenv("MTM5MzQ1NzUwNjc4ODgzOTUzNw.GTfqQX.3aH9109-F1CTSJ1oSUlJZ1WXFvIH5Wcg5CUt7E")

intents = Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # for slash commands


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await tree.sync()
        print(f"🔧 Synced {len(synced)} slash commands")
    except Exception as e:
        print("Failed to sync commands:", e)


@tree.command(name="backup", description="サーバーのメッセージをバックアップします")
async def backup_command(interaction: Interaction):
    await interaction.response.defer()
    backup_status[interaction.guild_id] = {"running": True, "progress": 0, "start": time.time()}

    await interaction.followup.send("📦 バックアップを開始します。少々お待ちください...")

    # ダミー処理（本来はここでメッセージを取得して保存）
    for i in range(5):  # 本物ではチャンネルループなど
        await asyncio.sleep(1)
        backup_status[interaction.guild_id]["progress"] = (i + 1) * 20

    backup_status[interaction.guild_id]["running"] = False
    backup_status[interaction.guild_id]["end"] = time.time()

    await interaction.followup.send("✅ バックアップが完了しました。")


@tree.command(name="status", description="バックアップの進捗を確認します")
async def status_command(interaction: Interaction):
    status = backup_status.get(interaction.guild_id)
    if not status:
        await interaction.response.send_message("🔍 バックアップ処理は開始されていません。", ephemeral=True)
        return

    if status["running"]:
        await interaction.response.send_message(
            f"⏳ バックアップ中です: {status['progress']}% 完了", ephemeral=True)
    else:
        duration = round(status["end"] - status["start"], 2)
        await interaction.response.send_message(
            f"✅ バックアップ完了（所要時間: {duration} 秒）", ephemeral=True)


@tree.command(name="restore", description="バックアップデータを指定チャンネルに復元します")
@app_commands.describe(url="バックアップファイルのURL")
async def restore_command(interaction: Interaction, url: str):
    await interaction.response.send_message(f"🔄 復元機能（URL: {url}）は現在準備中です。", ephemeral=True)


bot.run('MTM5MzQ1NzUwNjc4ODgzOTUzNw.GTfqQX.3aH9109-F1CTSJ1oSUlJZ1WXFvIH5Wcg5CUt7E')
