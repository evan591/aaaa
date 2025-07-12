import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")


@bot.command()
@commands.has_permissions(administrator=True)
async def backup(ctx, channel_id: int = None):
    """チャンネルのメッセージをバックアップする"""
    channel = ctx.guild.get_channel(channel_id) if channel_id else ctx.channel

    if not isinstance(channel, discord.TextChannel):
        await ctx.send("❌ 指定されたチャンネルはテキストチャンネルではありません。")
        return

    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        messages.append({
            "author": message.author.name,
            "content": message.content,
            "timestamp": str(message.created_at),
        })

    file_name = f"{channel.id}_backup.json"
    file_path = os.path.join(BACKUP_DIR, file_name)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)

    await ctx.send(f"✅ メッセージのバックアップが完了しました: `{file_name}`")


@bot.command()
@commands.has_permissions(administrator=True)
async def restore(ctx, filename: str):
    """バックアップファイルからメッセージを復元する"""
    file_path = os.path.join(BACKUP_DIR, filename)

    if not os.path.exists(file_path):
        await ctx.send("❌ 指定されたファイルが見つかりません。")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        messages = json.load(f)

    await ctx.send(f"♻️ `{filename}` の復元を開始します...")

    for msg in messages:
        content = f"**{msg['author']}**: {msg['content']}"
        await ctx.send(content)
        await asyncio.sleep(0.5)  # スパム防止のためのディレイ

    await ctx.send("✅ 復元が完了しました。")


bot.run('MTM5MzQ1NzUwNjc4ODgzOTUzNw.GTfqQX.3aH9109-F1CTSJ1oSUlJZ1WXFvIH5Wcg5CUt7E')
