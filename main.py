import subprocess

subprocess.Popen(["python", "bot.py"])
subprocess.Popen(["python", "music.py"])

# 終了しないように待機（必要に応じて）
import time
while True:
    time.sleep(10)
