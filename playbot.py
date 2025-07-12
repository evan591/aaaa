import discord
from discord.ext import commands
import yt_dlp
import asyncio

intents = discord.Intents.default()
intents.message_content = True  # 必須
bot = commands.Bot(command_prefix='/', intents=intents)

# 音声ソース設定
yt_dl_opts = {'format': 'bestaudio', 'noplaylist': True}
ffmpeg_opts = {'options': '-vn'}

@bot.event
async def on_ready():
    print(f'ログインしました: {bot.user.name}')

@bot.command()
async def play(ctx, url: str):
    # ボイスチャンネルに参加
    if ctx.author.voice is None:
        return await ctx.send("ボイスチャンネルに参加してから使ってください。")
    
    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)

    # YouTubeから音源取得
    with yt_dlp.YoutubeDL(yt_dl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info['url']

    # 音声再生
    source = await discord.FFmpegOpusAudio.from_probe(audio_url, **ffmpeg_opts)
    ctx.voice_client.stop()  # 既存の再生停止
    ctx.voice_client.play(source, after=lambda e: print('再生完了'))

    await ctx.send(f"再生中: {info['title']}")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("切断しました。")
    else:
        await ctx.send("Botはボイスチャンネルに接続していません。")

# あなたのBotのトークンに置き換えてください
bot.run('DISCORD_BOT_TOKEN')
