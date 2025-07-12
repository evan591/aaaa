import os
import asyncio
import yt_dlp
import discord
from discord import app_commands
from discord.ext import commands
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()

# 認証情報
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

# Spotify API認証
spotify = Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

yt_dl_opts = {
    'format': 'bestaudio',
    'quiet': True,
    'noplaylist': True
}
ffmpeg_opts = {'options': '-vn'}

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

queue = {}  # ギルドごとのキュー {guild_id: [url1, url2, ...]}

async def play_next(vc, guild_id):
    if queue[guild_id]:
        url = queue[guild_id].pop(0)
        with yt_dlp.YoutubeDL(yt_dl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info["url"]

        source = await discord.FFmpegOpusAudio.from_probe(audio_url, **ffmpeg_opts)
        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(vc, guild_id), bot.loop))

@tree.command(name="play", description="音楽を再生します（YouTube URL または Spotify URL/検索ワード）")
@app_commands.describe(query="YouTubeまたはSpotifyのURL、または検索語句")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    guild_id = interaction.guild.id

    # 音声チャンネル確認
    if interaction.user.voice is None:
        await interaction.followup.send("ボイスチャンネルに参加してください。")
        return
    channel = interaction.user.voice.channel

    # ボイス接続
    vc = interaction.guild.voice_client
    if not vc:
        vc = await channel.connect()
        queue[guild_id] = []

    # Spotify URL処理
    if "spotify.com/track" in query:
        track_id = query.split("/")[-1].split("?")[0]
        track = spotify.track(track_id)
        query = f"{track['name']} {track['artists'][0]['name']}"

    # YouTube検索（yt-dlp）
    if not query.startswith("http"):
        with yt_dlp.YoutubeDL({'quiet': True, 'default_search': 'ytsearch', 'noplaylist': True}) as ydl:
            info = ydl.extract_info(query, download=False)
            query = info['entries'][0]['webpage_url']

    # キューに追加
    queue[guild_id].append(query)
    await interaction.followup.send(f"キューに追加: {query}")

    # 再生開始
    if not vc.is_playing():
        await play_next(vc, guild_id)

@tree.command(name="skip", description="現在の曲をスキップします")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("スキップしました。")
    else:
        await interaction.response.send_message("再生中の音楽がありません。")

@tree.command(name="queue", description="再生キューを表示します")
async def show_queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    q = queue.get(guild_id, [])
    if not q:
        await interaction.response.send_message("キューは空です。")
    else:
        msg = "\n".join([f"{i+1}. {url}" for i, url in enumerate(q)])
        await interaction.response.send_message(f"再生キュー:\n{msg}")

@tree.command(name="stop", description="Botをボイスチャンネルから切断します")
async def stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("切断しました。")
    else:
        await interaction.response.send_message("Botは接続していません。")

@bot.event
async def on_ready():
    await tree.sync()
    print(f"{bot.user} でログインしました")

bot.run('DISCORD_BOT_TOKEN')

