import os
import logging
from datetime import datetime, timedelta
import yt_dlp
from instagrapi import Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# --- CONFIGURATION ---
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
INSTA_USER = "YOUR_INSTAGRAM_USERNAME"
INSTA_PASS = "YOUR_INSTAGRAM_PASSWORD"
SESSION_FILE = "insta_session.json"

# Conversation States
GET_LINK, EDIT_CAPTION, CHOOSE_TIMING, GET_SCHEDULE_TIME = range(4)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- INSTAGRAM CLIENT SETUP ---
cl = Client()

def login_instagram():
    if os.path.exists(SESSION_FILE):
        cl.load_settings(SESSION_FILE)
    try:
        cl.login(INSTA_USER, INSTA_PASS)
        cl.dump_settings(SESSION_FILE)
        logger.info("Instagram Logged In Successfully")
    except Exception as e:
        logger.error(f"Login failed: {e}")

# --- HELPER FUNCTIONS ---
def download_media(url):
    """Downloads video and returns (file_path, original_caption)"""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'quiet': True,
    }
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        caption = info.get('description') or info.get('title') or ""
        return filename, caption

async def upload_task(context: ContextTypes.DEFAULT_TYPE):
    """The actual function that uploads to Instagram"""
    job = context.job
    file_path = job.data['file_path']
    caption = job.data['caption']
    chat_id = job.data['chat_id']
    
    try:
        # Use clip_upload for Reels
        cl.clip_upload(file_path, caption)
        await context.bot.send_message(chat_id=chat_id, text="✅ Reel uploaded successfully!")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Upload failed: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! Send me a YouTube Shorts or Instagram Reel link to get started.")
    return GET_LINK

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    await update.message.reply_text("📥 Downloading and processing video... please wait.")
    
    try:
        file_path, caption = download_media(url)
        context.user_data['file_path'] = file_path
        context.user_data['caption'] = caption
        
        keyboard = [[InlineKeyboardButton("Keep Original", callback_query_data="keep")],
                    [InlineKeyboardButton("Edit Caption", callback_query_data="edit")]]
        
        await update.message.reply_text(
            f"🎬 **Video Downloaded!**\n\n**Original Caption:**\n{caption[:200]}...",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return EDIT_CAPTION
    except Exception as e:
        await update.message.reply_text(f"❌ Error downloading: {e}")
        return ConversationHandler.END

async def caption_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "keep":
        return await ask_timing(query.message, context)
    else:
        await query.message.reply_text("Please send the new caption you want to use:")
        return GET_SCHEDULE_TIME # Recycling state for caption input

async def receive_new_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['caption'] = update.message.text
    return await ask_timing(update.message, context)

async def ask_timing(msg, context):
    keyboard = [[InlineKeyboardButton("Upload Now", callback_query_data="now")],
                [InlineKeyboardButton("Schedule Later", callback_query_data="schedule")]]
    await msg.reply_text("⏰ When should I upload this?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_TIMING

async def handle_timing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "now":
        await query.message.reply_text("🚀 Uploading now...")
        # Add a job to run immediately
        context.job_queue.run_once(upload_task, 0, data={
            'file_path': context.user_data['file_path'],
            'caption': context.user_data['caption'],
            'chat_id': update.effective_chat.id
        })
        return ConversationHandler.END
    else:
        await query.message.reply_text("Send me the schedule time in minutes from now (e.g., 60 for 1 hour):")
        return GET_SCHEDULE_TIME

async def handle_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        minutes = int(update.message.text)
        delay = minutes * 60
        
        context.job_queue.run_once(upload_task, delay, data={
            'file_path': context.user_data['file_path'],
            'caption': context.user_data['caption'],
            'chat_id': update.effective_chat.id
        })
        
        await update.message.reply_text(f"📅 Scheduled! The video will be posted in {minutes} minutes.")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Please send a valid number of minutes.")
        return GET_SCHEDULE_TIME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Process cancelled.")
    return ConversationHandler.END

def main():
    login_instagram()
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link), CommandHandler("start", start)],
        states={
            GET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)],
            EDIT_CAPTION: [CallbackQueryHandler(caption_choice)],
            CHOOSE_TIMING: [CallbackQueryHandler(handle_timing)],
            GET_SCHEDULE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_caption), # Handles caption edit
                               MessageHandler(filters.Regex(r'^\d+$'), handle_schedule)] # Handles minutes
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()