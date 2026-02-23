import os
import logging
from instagrapi import Client
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = "8421640384:AAEwhC-l296tD_SKwSIclceEEtge3sb4qhc"
INSTA_USER = "ig_akash_thakur1"
INSTA_PASS = "gr555ebrt"
SESSION_FILE = "insta_session.json"
UPLOAD_DIR = "uploads"

logging.basicConfig(level=logging.INFO)

cl = Client()

def login_instagram():
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
    cl.login(INSTA_USER, INSTA_PASS)
    cl.dump_settings(SESSION_FILE)
    print("Instagram logged in")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a video and I will upload it to Instagram Reels 📤"
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video

    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    file = await context.bot.get_file(video.file_id)
    path = f"{UPLOAD_DIR}/{video.file_id}.mp4"

    await file.download_to_drive(path)

    await update.message.reply_text("Uploading to Instagram... ⏳")

    try:
        cl.clip_upload(path, caption="Uploaded via Telegram bot 🚀")
        await update.message.reply_text("✅ Uploaded successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Upload failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)

def main():
    login_instagram()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
