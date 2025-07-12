import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'extract_flat': False,
}

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

queue = []
loop_song = False
disconnect_timer = {}

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

def get_source(url):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'url': info['url'],
            'title': info.get('title'),
            'webpage_url': info.get('webpage_url'),
        }

async def play_next(vc, interaction):
    global queue, loop_song
    if loop_song and queue:
        song = queue[0]
    elif queue:
        song = queue.pop(0)
    else:
        return

    source = await discord.FFmpegOpusAudio.from_probe(song['url'], **FFMPEG_OPTIONS)
    vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(vc, interaction), bot.loop))

    embed = discord.Embed(title="🎵 Now Playing", description=f"[{song['title']}]({song['webpage_url']})", color=0x1DB954)
    await interaction.followup.send(embed=embed)

@tree.command(name="play", description="YouTubeの音楽を再生します")
@app_commands.describe(url="YouTubeのURL")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()

    voice = interaction.user.voice
    if not voice:
        return await interaction.followup.send("❌ VCに参加してからコマンドを使ってください")

    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)

    try:
        data = get_source(url)
    except Exception as e:
        return await interaction.followup.send(f"❌ 再生に失敗しました: {e}")

    if voice_client and voice_client.is_connected():
        queue.append(data)
        await interaction.followup.send(f"✅ キューに追加: [{data['title']}]({data['webpage_url']})")
    else:
        vc = await voice.channel.connect()
        queue.append(data)
        await play_next(vc, interaction)

@tree.command(name="stop", description="音楽を停止します")
async def stop(interaction: discord.Interaction):
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("⏹️ 再生を停止しました")
    else:
        await interaction.response.send_message("❌ 再生中の音楽がありません")

@tree.command(name="leave", description="ボイスチャンネルから退出します")
async def leave(interaction: discord.Interaction):
    voice_client = discord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice_client:
        await voice_client.disconnect()
        await interaction.response.send_message("👋 VCから退出しました")
    else:
        await interaction.response.send_message("❌ VCに接続していません")

@tree.command(name="loop", description="現在の曲のループをON/OFF切り替えます")
async def loop(interaction: discord.Interaction):
    global loop_song
    loop_song = not loop_song
    await interaction.response.send_message(f"🔁 ループモード: {'有効' if loop_song else '無効'}")

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

async def auto_disconnect(vc):
    if vc.is_connected():
        await vc.disconnect()
        print(f"⏰ 自動でVCから切断しました: {vc.guild.name}")

# 実行
bot.run("MTM5MzQ1NzUwNjc4ODgzOTUzNw.G-Dtub.9MEz-V7cbS3ZQ1mQYcWYxklZSjQOPDuNM0VGqs")
