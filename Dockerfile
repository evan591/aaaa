FROM python:3.11-slim

# 必要なシステムパッケージのインストール
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# 作業ディレクトリの作成
WORKDIR /app

# 依存ファイルのコピーとインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリコードのコピー
COPY . .

# 起動コマンド
CMD ["python", "main.py"]
