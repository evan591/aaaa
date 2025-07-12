import subprocess

subprocess.Popen(["python", "file1.py"])
subprocess.Popen(["python", "file2.py"])

# 終了しないように待機（必要に応じて）
import time
while True:
    time.sleep(10)
