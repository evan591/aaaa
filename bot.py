import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import json
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# バックアップ用の状態管理（例）
backup_status = {
    "is_backup_running": False,
    "progress": 0,
}

# --- バックアップ関数 ---
async def backup_channel(channel: discord.TextChannel):
    backup_status["is_backup_running"] = True
    backup_status["progress"] = 0

    messages_data = []
    async for msg in channel.history(limit=None, oldest_first=True):
        # メッセージの基本情報
        msg_info = {
            "id": msg.id,
            "content": msg.content,
            "author_name": msg.author.name,
            "author_id": msg.author.id,
            "created_at": str(msg.created_at),
            "attachments": [],
            "embeds": [],
        }
        # 添付ファイルを保存（URLのみ）
        for attach in msg.attachments:
            msg_info["attachments"].append({
                "url": attach.url,
                "filename": attach.filename,
                "content_type": attach.content_type,
            })
        # 埋め込みを簡易保存
        for embed in msg.embeds:
            msg_info["embeds"].append(embed.to_dict())

        messages_data.append(msg_info)
        backup_status["progress"] += 1

    backup_status["is_backup_running"] = False
    return messages_data

# --- 復元関数 ---
async def restore_backup(channel: discord.TextChannel, backup_data):
    # 元のユーザーになりすますにはWebhookを使う必要がある
    webhook = await channel.create_webhook(name="RestoreBotWebhook")
    try:
        for msg in backup_data:
            content = msg["content"]
            username = msg["author_name"]
            avatar_url = None  # ここは取得難しいので割愛
            files = []

            # 添付ファイルをダウンロードしてファイル化
            for attach_info in msg["attachments"]:
                async with aiohttp.ClientSession() as session:
                    async with session.get(attach_info["url"]) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            files.append(discord.File(fp=discord.BytesIO(data), filename=attach_info["filename"]))

            # Webhookでメッセージ送信
            await webhook.send(
                content=content,
                username=username,
                files=files,
                wait=True,
            )
            # 送信が速すぎるとDiscordに怒られるので軽く待つ
            await asyncio.sleep(1)
    finally:
        await webhook.delete()

# --- スラッシュコマンド ---

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged in as {bot.user}!")

@bot.tree.command(name="backup", description="指定したチャンネルのメッセージをバックアップします")
@app_commands.describe(channel="バックアップするテキストチャンネル")
async def backup(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(thinking=True)
    if backup_status["is_backup_running"]:
        await interaction.followup.send("すでにバックアップ処理が実行中です。しばらく待ってください。")
        return

    messages_data = await backup_channel(channel)
    # バックアップデータをJSONで保存（ここは単純にファイルアップロードに変更可能）
    json_str = json.dumps(messages_data, ensure_ascii=False, indent=2)
    file = discord.File(fp=discord.BytesIO(json_str.encode("utf-8")), filename=f"backup_{channel.id}.json")
    await interaction.followup.send(f"{channel.name} のバックアップが完了しました。", file=file)

@bot.tree.command(name="restore", description="バックアップファイルを指定してメッセージを復元します")
@app_commands.describe(file_url="復元するバックアップファイルのURL")
async def restore(interaction: discord.Interaction, file_url: str):
    await interaction.response.defer(thinking=True)
    # ファイルURLからJSONを取得して復元
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            if resp.status != 200:
                await interaction.followup.send("ファイルの取得に失敗しました。URLが正しいか確認してください。")
                return
            text = await resp.text()
            try:
                backup_data = json.loads(text)
            except Exception:
                await interaction.followup.send("ファイルの内容がJSON形式ではありません。")
                return

    # メッセージの復元を行うチャンネルはコマンド実行チャンネルとする
    await restore_backup(interaction.channel, backup_data)
    await interaction.followup.send("復元処理が完了しました。")

@bot.tree.command(name="status", description="バックアップの進行状況を確認します")
async def status(interaction: discord.Interaction):
    if backup_status["is_backup_running"]:
        await interaction.response.send_message(f"バックアップ実行中。現在 {backup_status['progress']} 件処理済みです。")
    else:
        await interaction.response.send_message("現在バックアップ処理は実行されていません。")

@bot.tree.command(name="help", description="使い方を表示します")
async def help(interaction: discord.Interaction):
    help_text = """
**📚 コマンド一覧**  
`/backup [channel]` - 指定したチャンネルのバックアップを取得します。  
`/restore <ファイルURL>` - バックアップJSONファイルを指定してメッセージを復元します。  
`/status` - バックアップの進行状況を表示します。  
`/help` - このヘルプを表示します。
"""
    await interaction.response.send_message(help_text, ephemeral=True)

# Botトークンは環境変数や外部ファイルで管理推奨
bot.run("MTM5MzQ1NzUwNjc4ODgzOTUzNw.GTfqQX.3aH9109-F1CTSJ1oSUlJZ1WXFvIH5Wcg5CUt7E")
