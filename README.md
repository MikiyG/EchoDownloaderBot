# EchoDownloaderBot
A Telegram Bot to basically download any video!

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install required Python packages
pip install python-telegram-bot yt-dlp python-dotenv

# Install system dependencies
sudo apt install ffmpeg aria2 -y

# Create your .env file with your Telegram Bot Token
echo "TELEGRAM_TOKEN=your_token_here" > .env

# Run the bot
python main.py

# Instructions:
# 1. Open https://t.me/EchoDLBot
# 2. Type /start
# 3. Upload your video/media link
# 4. Enjoy 🎉
