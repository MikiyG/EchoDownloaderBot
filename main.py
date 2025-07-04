import os
import tempfile
import shutil
import logging
import sys
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)
import yt_dlp

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logging.error("No TELEGRAM_TOKEN set in environment.")
    sys.exit(1)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
ASK_LINK, ASK_FORMAT = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler for /start command: ask user for a link."""
    await update.message.reply_text("👋 Hi! Send me the link of the video you want to download.")
    return ASK_LINK

async def ask_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler for receiving a URL: validate and ask format choice."""
    url = update.message.text.strip()
    if not url.lower().startswith(("http://", "https://")):
        await update.message.reply_text("❗️ Please send a valid URL (must start with http:// or https://).")
        return ASK_LINK

    context.user_data['url'] = url
    keyboard = [
        [InlineKeyboardButton("Audio 🎵", callback_data='audio'),
         InlineKeyboardButton("Video 🎥", callback_data='video')]
    ]
    await update.message.reply_text(
        "Great! Do you want audio or video?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ASK_FORMAT

async def handle_format_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler for format choice buttons: download, countdown, send, and loop."""
    query = update.callback_query
    await query.answer()
    choice = query.data  # 'audio' or 'video'
    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text("❌ Something went wrong (missing URL). Please /start again.")
        return ConversationHandler.END

    # Initial status message
    status_msg = await query.edit_message_text(f"🔄 Downloading your {choice}…")

    temp_dir = tempfile.mkdtemp()
    try:
        # Run download in thread to avoid blocking
        file_path = await asyncio.get_event_loop().run_in_executor(
            None, download_media, url, temp_dir, choice
        )

        # Countdown before sending
        for sec in range(5, 0, -1):
            await status_msg.edit_text(f"🚀 Sending your {choice} in {sec} second{'s' if sec>1 else ''}…")
            await asyncio.sleep(1)

        # Send media file
        with open(file_path, 'rb') as fh:
            if choice == 'video':
                await query.message.reply_video(video=fh)
            else:
                await query.message.reply_audio(audio=fh)

        # Prompt for next link
        await query.message.reply_text("✅ Done! Send me another link (or /cancel to stop).")
        return ASK_LINK

    except Exception as e:
        logger.exception("Download error")
        await query.message.reply_text(f"❌ Error during download: {e}")
        return ASK_LINK

    finally:
        # Clean up
        shutil.rmtree(temp_dir, ignore_errors=True)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler for /cancel: end conversation."""
    await update.message.reply_text("👋 Operation cancelled. Use /start to download again.")
    return ConversationHandler.END

def download_media(url: str, download_dir: str, fmt: str) -> str:
    """
    Download media via yt-dlp with resumable, multi-connection settings.
    Returns the path to the downloaded file.
    """
    ydl_opts = {
        'format': 'bestaudio/best' if fmt == 'audio' else 'bestvideo+bestaudio/best',
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'continuedl': True,            # resume partial downloads
        'retries': 10,
        'fragment_retries': 10,
        'socket_timeout': 10,
        'http_chunk_size': 10_485_760, # 10 MB chunks
        # use aria2c if installed for multi-connection speed
        'external_downloader': 'aria2c',
        'external_downloader_args': ['-x', '16', '-k', '1M'],
        'quiet': True,
    }

    if fmt == 'audio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if fmt == 'audio':
            filename = os.path.splitext(filename)[0] + '.mp3'
        return filename

def main():
    """Entrypoint: setup bot and start polling."""
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_format)],
            ASK_FORMAT: [CallbackQueryHandler(handle_format_choice)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            MessageHandler(filters.ALL, start)  # ⬅️ Catch-all to restart from /start
        ],
        allow_reentry=True  # ⬅️ Allow reentering conversation from any state
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler('help', lambda u, c: u.message.reply_text(
        '/start – begin download\n/cancel – stop'
    )))

    logger.info("Bot is starting up…")
    app.run_polling()


if __name__ == '__main__':
    main()
